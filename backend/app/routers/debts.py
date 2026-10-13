from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import Debt, DebtPayment, User
from ..schemas import DebtIn, DebtOut, DebtPaymentIn, DebtPaymentOut
from ..services import finance

router = APIRouter(prefix="/debts", tags=["deudas"])


@router.get("", response_model=list[DebtOut])
def list_debts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Debt).where(Debt.user_id == user.id).order_by(Debt.id)).all()


@router.post("", response_model=DebtOut, status_code=201)
def create_debt(data: DebtIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    debt = Debt(user_id=user.id, **data.model_dump())
    db.add(debt)
    db.commit()
    db.refresh(debt)
    return debt


@router.delete("/{debt_id}", status_code=204)
def delete_debt(debt_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    debt = owned(db, Debt, debt_id, user)
    db.query(DebtPayment).filter(DebtPayment.debt_id == debt.id).delete()
    db.delete(debt)
    db.commit()


@router.get("/{debt_id}/schedule")
def schedule(debt_id: int, extra: float = Query(0, ge=0),
             db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Proyección de pagos hasta saldar la deuda, con abono extra opcional.

    Compara contra el escenario sin extra para mostrar cuánto interés te ahorras.
    """
    debt = owned(db, Debt, debt_id, user)
    r = finance.monthly_rate(float(debt.rate), debt.rate_type)
    balance = float(debt.current_balance)
    if debt.monthly_payment:
        payment = float(debt.monthly_payment)
    elif debt.term_months:
        payment = finance.loan_payment(balance, r, debt.term_months)
    else:
        raise HTTPException(422, "Define la cuota mensual o el plazo para proyectar")
    try:
        base = finance.amortize(balance, r, payment)
        plan = finance.amortize(balance, r, payment, extra)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {
        "monthly_rate_pct": round(r * 100, 4),
        "payment": round(payment, 2),
        "extra": extra,
        "months": plan["months"],
        "total_interest": plan["total_interest"],
        "total_paid": plan["total_paid"],
        "months_saved": base["months"] - plan["months"],
        "interest_saved": round(base["total_interest"] - plan["total_interest"], 2),
        "rows": plan["rows"],
    }


@router.post("/{debt_id}/payments", response_model=DebtPaymentOut, status_code=201)
def register_payment(debt_id: int, data: DebtPaymentIn,
                     db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Registra un pago real: separa interés y capital y baja el saldo."""
    debt = owned(db, Debt, debt_id, user)
    r = Decimal(str(finance.monthly_rate(float(debt.rate), debt.rate_type)))
    interest = (debt.current_balance * r).quantize(Decimal("0.01"))
    principal = data.amount - interest
    if principal > debt.current_balance:
        principal = debt.current_balance
    debt.current_balance -= principal
    pay = DebtPayment(debt_id=debt.id, amount=data.amount, interest=interest,
                      principal=principal, date=data.date)
    db.add(pay)
    db.commit()
    db.refresh(pay)
    return pay


@router.get("/{debt_id}/payments", response_model=list[DebtPaymentOut])
def list_payments(debt_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned(db, Debt, debt_id, user)
    return db.scalars(select(DebtPayment).where(DebtPayment.debt_id == debt_id)
                      .order_by(DebtPayment.date.desc(), DebtPayment.id.desc())).all()
