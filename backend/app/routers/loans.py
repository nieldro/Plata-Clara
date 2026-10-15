from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import Account, Category, Loan, LoanPayment, Transaction, User
from ..schemas import LoanIn, LoanPaymentIn, LoanUpdate, SplitIn
from ..services import loans as svc
from ..services.ledger import apply_to_card

router = APIRouter(tags=["préstamos"])


def _payments(db: Session, loan_id: int) -> list[LoanPayment]:
    return list(db.scalars(select(LoanPayment).where(LoanPayment.loan_id == loan_id)
                           .order_by(LoanPayment.date, LoanPayment.id)))


def _detail(db: Session, loan: Loan) -> dict:
    pays = _payments(db, loan.id)
    out = svc.loan_out(loan, sum((p.amount for p in pays), Decimal(0)))
    out["payments"] = [{"id": p.id, "amount": p.amount, "date": p.date, "note": p.note,
                        "in_account": p.transaction_id is not None} for p in pays]
    return out


@router.get("/loans")
def list_loans(status: str = Query("open", pattern="^(open|settled|all)$"),
               db: Session = Depends(get_db), user: User = Depends(current_user)):
    loans = list(db.scalars(select(Loan).where(Loan.user_id == user.id).order_by(Loan.date.desc(), Loan.id.desc())))
    paid = svc.paid_amounts(db, [l.id for l in loans])
    items = [svc.loan_out(l, paid.get(l.id) or Decimal(0)) for l in loans]
    if status == "open":
        items = [i for i in items if not i["settled"]]
    elif status == "settled":
        items = [i for i in items if i["settled"]]
    return items


@router.get("/loans/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Cuánto te deben, cuánto debes y el saldo neto con cada persona."""
    loans = list(db.scalars(select(Loan).where(Loan.user_id == user.id)))
    paid = svc.paid_amounts(db, [l.id for l in loans])
    owed_to_me = i_owe = Decimal(0)
    per_person: dict[str, Decimal] = defaultdict(Decimal)
    overdue = 0
    for l in loans:
        item = svc.loan_out(l, paid.get(l.id) or Decimal(0))
        if item["settled"]:
            continue
        signed = item["outstanding"] if l.direction == "lent" else -item["outstanding"]
        per_person[l.person.strip().lower()] += signed
        if l.direction == "lent":
            owed_to_me += item["outstanding"]
        else:
            i_owe += item["outstanding"]
        overdue += item["overdue"]
    display = {l.person.strip().lower(): l.person.strip() for l in loans}
    people = sorted(({"person": display[k], "net": v} for k, v in per_person.items() if v != 0),
                    key=lambda p: -abs(p["net"]))
    return {"owed_to_me": owed_to_me, "i_owe": i_owe, "net": owed_to_me - i_owe, "overdue": overdue, "people": people}


@router.post("/loans", status_code=201)
def create_loan(data: LoanIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if data.account_id:
        owned(db, Account, data.account_id, user)
    loan = Loan(user_id=user.id, person=data.person.strip(), direction=data.direction, amount=data.amount,
                date=data.date, due_date=data.due_date, note=data.note)
    db.add(loan)
    db.flush()
    if data.account_id:  # prestar saca plata de la cuenta; que te presten la mete
        kind = "expense" if data.direction == "lent" else "income"
        verb = "Préstamo a" if data.direction == "lent" else "Préstamo de"
        svc.money_move(db, user.id, data.account_id, kind, data.amount, data.date, f"{verb} {loan.person}", loan.id)
    db.commit()
    return _detail(db, loan)


@router.get("/loans/{loan_id}")
def get_loan(loan_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _detail(db, owned(db, Loan, loan_id, user))


@router.patch("/loans/{loan_id}")
def update_loan(loan_id: int, data: LoanUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    loan = owned(db, Loan, loan_id, user)
    if data.person is not None:
        loan.person = data.person.strip()
    if data.note is not None:
        loan.note = data.note
    if data.clear_due_date:
        loan.due_date = None
    elif data.due_date is not None:
        if data.due_date < loan.date:
            raise HTTPException(422, "La fecha límite no puede ser anterior al préstamo")
        loan.due_date = data.due_date
    db.commit()
    return _detail(db, loan)


@router.post("/loans/{loan_id}/payments", status_code=201)
def add_payment(loan_id: int, data: LoanPaymentIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Registra un abono: alguien te devuelve plata (lent) o tú pagas lo que debes (borrowed)."""
    loan = owned(db, Loan, loan_id, user)
    outstanding = loan.amount - sum((p.amount for p in _payments(db, loan.id)), Decimal(0))
    if data.amount > outstanding:
        raise HTTPException(422, f"El abono supera lo que falta ({outstanding:.2f})")
    if data.account_id:
        owned(db, Account, data.account_id, user)
    pay = LoanPayment(loan_id=loan.id, amount=data.amount, date=data.date, note=data.note)
    db.add(pay)
    db.flush()
    if data.account_id:
        kind = "income" if loan.direction == "lent" else "expense"
        verb = "Abono de" if loan.direction == "lent" else "Pago a"
        tx = svc.money_move(db, user.id, data.account_id, kind, data.amount, data.date, f"{verb} {loan.person}", loan.id)
        pay.transaction_id = tx.id
    db.commit()
    return _detail(db, loan)


@router.delete("/loans/{loan_id}/payments/{payment_id}")
def delete_payment(loan_id: int, payment_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    loan = owned(db, Loan, loan_id, user)
    pay = db.get(LoanPayment, payment_id)
    if not pay or pay.loan_id != loan.id:
        raise HTTPException(404, "No encontrado")
    tx = db.get(Transaction, pay.transaction_id) if pay.transaction_id else None
    db.delete(pay)
    db.flush()
    if tx:
        svc.remove_tx(db, tx)
    db.commit()
    return _detail(db, loan)


@router.delete("/loans/{loan_id}", status_code=204)
def delete_loan(loan_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Borra el préstamo y revierte lo que haya movido en tus cuentas."""
    loan = owned(db, Loan, loan_id, user)
    db.execute(delete(LoanPayment).where(LoanPayment.loan_id == loan.id))
    db.flush()
    for tx in list(db.scalars(select(Transaction).where(Transaction.loan_id == loan.id))):
        svc.remove_tx(db, tx)
    db.flush()
    db.delete(loan)
    db.commit()


@router.post("/splits", status_code=201)
def split_expense(data: SplitIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Pagaste una cuenta entre varios: tu parte es gasto tuyo y lo de los demás queda como «te deben»."""
    owned(db, Account, data.account_id, user)
    if data.category_id:
        owned(db, Category, data.category_id, user)

    people = data.participants
    if people[0].amount is None:
        each, mine = svc.equal_shares(data.total, len(people))
        shares = [each] * len(people)
    else:
        shares = [p.amount for p in people]
        mine = data.total - sum(shares)
        if mine < 0:
            raise HTTPException(422, "Lo que le cobras a los demás supera el total de la cuenta")
    label = data.note or "Cuenta compartida"

    if mine > 0:  # solo tu parte cuenta como gasto (y entra al presupuesto de la categoría)
        tx = Transaction(user_id=user.id, account_id=data.account_id, category_id=data.category_id, kind="expense",
                         amount=mine, date=data.date, note=f"{label} (mi parte)")
        db.add(tx)
        db.flush()
        apply_to_card(db, tx.account_id, "expense", mine, +1)

    created = []
    for p, share in zip(people, shares):
        loan = Loan(user_id=user.id, person=p.person.strip(), direction="lent", amount=share, date=data.date,
                    due_date=data.due_date, note=label)
        db.add(loan)
        db.flush()
        # el dinero que adelantaste por ellos también salió de tu cuenta
        svc.money_move(db, user.id, data.account_id, "expense", share, data.date, f"{label}: parte de {loan.person}", loan.id)
        created.append(loan)
    db.commit()
    return {"my_share": mine, "loans": [_detail(db, l) for l in created]}
