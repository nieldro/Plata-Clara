import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from .. import clock
from ..db import get_db
from ..deps import current_user, owned
from ..institutions import INSTITUTIONS, SLUGS
from ..models import (Account, Attachment, Budget, Category, CategoryRule, Debt, DebtPayment, LoanPayment,
                      Recurring, Tag, Transaction, User, transaction_tags)
from ..schemas import (AccountIn, AccountOut, AccountUpdate, CategoryIn, CategoryOut,
                       TransactionIn, TransactionOut, TransactionUpdate, TransferIn)
from ..services.ledger import apply_to_card
from ..services.queries import account_balances
from ..services.rules import learn
from ..services.tags import normalize, set_tags
from ..services.uploads import purge_files_for

router = APIRouter(tags=["movimientos"])


# ---------- cuentas ----------
def _account_out(acc: Account, moved: dict, debt: Debt | None) -> AccountOut:
    item = AccountOut.model_validate(acc)
    if acc.type == "credit_card":
        owed = debt.current_balance if debt else Decimal(0)
        item.balance = -owed
        if acc.credit_limit is not None:
            item.available = acc.credit_limit - owed
    else:
        item.balance = acc.initial_balance + (moved.get(acc.id) or 0)
    return item


@router.get("/institutions")
def institutions():
    """Catálogo de entidades colombianas (bancos, billeteras, inversión)."""
    return INSTITUTIONS


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    moved = account_balances(db, user.id)
    debts = {d.id: d for d in db.scalars(select(Debt).where(Debt.user_id == user.id))}
    accounts = db.scalars(select(Account).where(Account.user_id == user.id).order_by(Account.id))
    return [_account_out(a, moved, debts.get(a.debt_id)) for a in accounts]


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(data: AccountIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if data.institution and data.institution not in SLUGS:
        raise HTTPException(422, "Entidad desconocida: usa el nombre libre para una entidad no listada")
    fields = data.model_dump(exclude={"rate", "rate_type", "monthly_payment", "due_day"})
    if data.institution:
        fields["institution_name"] = None
    debt = None
    if data.type == "credit_card":
        entity = next((i["name"] for i in INSTITUTIONS if i["slug"] == data.institution), data.institution_name)
        debt = Debt(
            user_id=user.id, name=f"{entity} · {data.name}", kind="credit_card",
            original_amount=data.credit_limit or data.initial_balance,
            current_balance=data.initial_balance, rate=data.rate, rate_type=data.rate_type,
            monthly_payment=data.monthly_payment, due_day=data.due_day,
        )
        db.add(debt)
        db.flush()
        fields.update(initial_balance=Decimal(0), debt_id=debt.id)
    acc = Account(user_id=user.id, **fields)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return _account_out(acc, {}, debt)


CARD_FIELDS = {"credit_limit", "rate", "rate_type", "monthly_payment", "due_day"}


@router.patch("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: int, data: AccountUpdate, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    """Edita el nombre, el saldo inicial o (en tarjetas) el cupo, la tasa, el pago habitual y el día de pago."""
    acc = owned(db, Account, account_id, user)
    changes = data.model_dump(exclude_unset=True)
    is_card = acc.type == "credit_card"
    if not is_card and CARD_FIELDS & changes.keys():
        raise HTTPException(422, "El cupo, la tasa y el pago solo se pueden editar en tarjetas de crédito")
    if is_card and "initial_balance" in changes:
        raise HTTPException(422, "El saldo de una tarjeta es su deuda: se mueve con gastos y abonos")

    if "name" in changes:
        acc.name = changes["name"]
    if "initial_balance" in changes:
        acc.initial_balance = changes["initial_balance"]
    debt = db.get(Debt, acc.debt_id) if acc.debt_id else None
    if is_card:
        if "credit_limit" in changes:
            acc.credit_limit = changes["credit_limit"]
        if debt:
            for field in ("rate", "rate_type", "monthly_payment", "due_day"):
                if field in changes:
                    setattr(debt, field, changes[field])
            if "name" in changes:  # la deuda se llama «Entidad · nombre de la tarjeta»
                entity = next((i["name"] for i in INSTITUTIONS if i["slug"] == acc.institution), acc.institution_name or "")
                debt.name = f"{entity} · {acc.name}"
    db.commit()
    db.refresh(acc)
    return _account_out(acc, account_balances(db, user.id), debt)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    acc = owned(db, Account, account_id, user)
    tx_ids = list(db.scalars(select(Transaction.id).where(Transaction.account_id == acc.id)))
    purge_files_for(db, user.id, tx_ids)
    for part in range(0, len(tx_ids), 400):  # en trozos: SQLite limita las variables por consulta
        chunk = tx_ids[part:part + 400]
        db.execute(delete(transaction_tags).where(transaction_tags.c.transaction_id.in_(chunk)))
        db.execute(delete(Attachment).where(Attachment.transaction_id.in_(chunk)))
        db.execute(update(LoanPayment).where(LoanPayment.transaction_id.in_(chunk)).values(transaction_id=None))
    db.query(Transaction).filter(Transaction.account_id == acc.id).delete()
    db.query(Recurring).filter(Recurring.account_id == acc.id).delete()
    debt_id = acc.debt_id
    db.delete(acc)
    if debt_id:
        db.flush()
        db.query(DebtPayment).filter(DebtPayment.debt_id == debt_id).delete()
        db.query(Debt).filter(Debt.id == debt_id).delete()
    db.commit()


# ---------- categorías ----------
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Category).where(Category.user_id == user.id).order_by(Category.kind, Category.name)).all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    exists = db.scalar(select(Category.id).where(
        Category.user_id == user.id, Category.kind == data.kind, func.lower(Category.name) == data.name.lower()))
    if exists:
        kind = "de ingreso" if data.kind == "income" else "de gasto"
        raise HTTPException(409, f"Ya tienes una categoría «{data.name}» {kind}")
    cat = Category(user_id=user.id, **data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Borra una categoría; sus movimientos quedan «sin categoría» y se quitan sus presupuestos y recurrentes."""
    cat = owned(db, Category, category_id, user)
    db.query(Transaction).filter(Transaction.category_id == cat.id).update({Transaction.category_id: None})
    db.query(Recurring).filter(Recurring.category_id == cat.id).update({Recurring.category_id: None})
    db.query(Budget).filter(Budget.category_id == cat.id).delete()
    db.query(CategoryRule).filter(CategoryRule.category_id == cat.id).delete()
    db.delete(cat)
    db.commit()


# ---------- movimientos ----------
@dataclass
class TxFilters:
    """Filtros del historial. Los comparten el listado y la exportación."""
    date_from: date | None = None
    date_to: date | None = None
    account_id: int | None = None
    category_id: int | None = None
    kind: str | None = None
    q: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    tag: str | None = None
    uncategorized: bool = False
    hide_transfers: bool = False

    def conditions(self, user_id: int) -> list:
        conds = [Transaction.user_id == user_id]
        if self.date_from:
            conds.append(Transaction.date >= self.date_from)
        if self.date_to:
            conds.append(Transaction.date <= self.date_to)
        if self.account_id:
            conds.append(Transaction.account_id == self.account_id)
        if self.category_id:
            conds.append(Transaction.category_id == self.category_id)
        if self.uncategorized:
            conds.append(Transaction.category_id.is_(None))
        if self.kind:
            conds.append(Transaction.kind == self.kind)
        if self.min_amount is not None:
            conds.append(Transaction.amount >= self.min_amount)
        if self.max_amount is not None:
            conds.append(Transaction.amount <= self.max_amount)
        if self.hide_transfers:
            conds.append(Transaction.transfer_id.is_(None))
        if self.tag and normalize(self.tag):
            tagged = (select(transaction_tags.c.transaction_id).join(Tag, Tag.id == transaction_tags.c.tag_id)
                      .where(Tag.user_id == user_id, Tag.name == normalize(self.tag)))
            conds.append(Transaction.id.in_(tagged))
        if self.q and self.q.strip():
            like = f"%{self.q.strip().lower()}%"
            by_category = select(Category.id).where(Category.user_id == user_id, func.lower(Category.name).like(like))
            conds.append(or_(func.lower(Transaction.note).like(like), Transaction.category_id.in_(by_category)))
        return conds


def tx_filters(
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: int | None = None,
    category_id: int | None = None,
    kind: Literal["income", "expense"] | None = None,
    q: str | None = Query(None, max_length=100, description="Texto en la nota o en el nombre de la categoría"),
    min_amount: Decimal | None = Query(None, ge=0),
    max_amount: Decimal | None = Query(None, ge=0),
    tag: str | None = Query(None, max_length=40, description="Nombre de una etiqueta"),
    uncategorized: bool = False,
    hide_transfers: bool = False,
) -> TxFilters:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "La fecha inicial no puede ser posterior a la final")
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise HTTPException(422, "El monto mínimo no puede superar al máximo")
    return TxFilters(date_from, date_to, account_id, category_id, kind, q, min_amount, max_amount, tag,
                     uncategorized, hide_transfers)


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    f: TxFilters = Depends(tx_filters),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    response: Response = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Historial con filtros combinables. El total sin paginar va en la cabecera X-Total-Count."""
    conds = f.conditions(user.id)
    total = db.scalar(select(func.count()).select_from(Transaction).where(*conds))
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    stmt = select(Transaction).where(*conds).order_by(Transaction.date.desc(), Transaction.id.desc())
    return db.scalars(stmt.limit(limit).offset(offset)).all()


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned(db, Account, data.account_id, user)
    if data.category_id:
        owned(db, Category, data.category_id, user)
    tx = Transaction(user_id=user.id, **data.model_dump(exclude={"tags"}))
    db.add(tx)
    set_tags(db, user.id, tx, data.tags)
    learn(db, user.id, tx.note, tx.category_id)
    apply_to_card(db, tx.account_id, tx.kind, tx.amount, +1)
    db.commit()
    db.refresh(tx)
    return tx


@router.patch("/transactions/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: int, data: TransactionUpdate,
                       db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Edita un movimiento. Si afecta una tarjeta, su deuda se recalcula (revierte lo viejo y aplica lo nuevo)."""
    tx = owned(db, Transaction, tx_id, user)
    if tx.transfer_id:
        raise HTTPException(422, "Las transferencias no se editan: bórrala y créala de nuevo")
    if tx.loan_id:
        raise HTTPException(422, "Este movimiento pertenece a un préstamo: gestiónalo desde «Préstamos»")
    changes = data.model_dump(exclude_unset=True, exclude={"clear_category"})
    if "account_id" in changes and changes["account_id"] is not None:
        owned(db, Account, changes["account_id"], user)
    if changes.get("category_id"):
        owned(db, Category, changes["category_id"], user)

    apply_to_card(db, tx.account_id, tx.kind, tx.amount, -1)
    for field in ("account_id", "category_id", "kind", "amount", "date", "note"):
        if changes.get(field) is not None:
            setattr(tx, field, changes[field])
    if data.clear_category:
        tx.category_id = None
    if data.tags is not None:
        set_tags(db, user.id, tx, data.tags)
    if changes.get("category_id") or changes.get("note"):
        learn(db, user.id, tx.note, tx.category_id)
    apply_to_card(db, tx.account_id, tx.kind, tx.amount, +1)
    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    tx = owned(db, Transaction, tx_id, user)
    if tx.loan_id:
        raise HTTPException(422, "Este movimiento pertenece a un préstamo: bórralo desde «Préstamos»")
    legs = [tx]
    if tx.transfer_id:  # borrar una pata de una transferencia borra las dos
        legs = list(db.scalars(select(Transaction).where(Transaction.transfer_id == tx.transfer_id,
                                                         Transaction.user_id == user.id)))
    purge_files_for(db, user.id, [leg.id for leg in legs])
    for leg in legs:
        apply_to_card(db, leg.account_id, leg.kind, leg.amount, -1)
        db.delete(leg)
    db.commit()


@router.post("/transfers", status_code=201)
def create_transfer(data: TransferIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Mueve dinero entre dos cuentas tuyas. Si el destino es una tarjeta, baja su deuda (pago)."""
    if data.from_account_id == data.to_account_id:
        raise HTTPException(422, "Elige dos cuentas distintas")
    owned(db, Account, data.from_account_id, user)
    owned(db, Account, data.to_account_id, user)
    tid = str(uuid.uuid4())
    for account_id, kind in ((data.from_account_id, "expense"), (data.to_account_id, "income")):
        db.add(Transaction(user_id=user.id, account_id=account_id, kind=kind, amount=data.amount,
                           date=data.date, note=data.note or "Transferencia", transfer_id=tid))
        apply_to_card(db, account_id, kind, data.amount, +1)
    db.commit()
    return {"transfer_id": tid}


@router.get("/summary/trend")
def trend(months: int = Query(6, ge=1, le=24),
          db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Ingresos y gastos de los últimos N meses (incluye meses vacíos)."""
    today = clock.today()
    first = today.year * 12 + today.month - 1 - (months - 1)
    buckets = {}
    for i in range(months):
        y, m = divmod(first + i, 12)
        key = f"{y}-{m + 1:02d}"
        buckets[key] = {"month": key, "income": 0.0, "expense": 0.0}
    start = date(first // 12, first % 12 + 1, 1)
    rows = db.execute(
        select(Transaction.date, Transaction.kind, Transaction.amount)
        .where(Transaction.user_id == user.id, Transaction.transfer_id.is_(None), Transaction.loan_id.is_(None),
               Transaction.date >= start)
    ).all()
    for d, kind, amount in rows:
        key = f"{d.year}-{d.month:02d}"
        if key in buckets:
            buckets[key][kind] += float(amount)
    return list(buckets.values())


@router.get("/summary")
def summary(month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
            db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Resumen de un mes (YYYY-MM): ingresos, gastos y gasto por categoría."""
    year, mon = int(month[:4]), int(month[5:])
    start = date(year, mon, 1)
    end = date(year + (mon == 12), mon % 12 + 1, 1)
    base = [Transaction.user_id == user.id, Transaction.transfer_id.is_(None), Transaction.loan_id.is_(None),
            Transaction.date >= start, Transaction.date < end]
    totals = dict(db.execute(
        select(Transaction.kind, func.sum(Transaction.amount)).where(*base).group_by(Transaction.kind)
    ).all())
    by_cat = db.execute(
        select(func.coalesce(Category.name, "Sin categoría"), func.sum(Transaction.amount))
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(*base, Transaction.kind == "expense")
        .group_by(Category.name)
        .order_by(func.sum(Transaction.amount).desc())
    ).all()
    income, expense = totals.get("income") or 0, totals.get("expense") or 0
    return {
        "month": month,
        "income": income,
        "expense": expense,
        "net": income - expense,
        "expense_by_category": [{"category": c, "total": t} for c, t in by_cat],
    }
