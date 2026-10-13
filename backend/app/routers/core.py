from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import Account, Category, Transaction, User
from ..schemas import (AccountIn, AccountOut, CategoryIn, CategoryOut,
                       TransactionIn, TransactionOut)

router = APIRouter(tags=["movimientos"])


# ---------- cuentas ----------
def _balances(db: Session, user_id: int) -> dict[int, float]:
    signed = case((Transaction.kind == "income", Transaction.amount), else_=-Transaction.amount)
    rows = db.execute(
        select(Transaction.account_id, func.sum(signed))
        .where(Transaction.user_id == user_id)
        .group_by(Transaction.account_id)
    ).all()
    return {a: s for a, s in rows}


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    moved = _balances(db, user.id)
    out = []
    for a in db.scalars(select(Account).where(Account.user_id == user.id).order_by(Account.id)):
        item = AccountOut.model_validate(a)
        item.balance = a.initial_balance + (moved.get(a.id) or 0)
        out.append(item)
    return out


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(data: AccountIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    acc = Account(user_id=user.id, **data.model_dump())
    db.add(acc)
    db.commit()
    db.refresh(acc)
    item = AccountOut.model_validate(acc)
    item.balance = acc.initial_balance
    return item


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    acc = owned(db, Account, account_id, user)
    db.query(Transaction).filter(Transaction.account_id == acc.id).delete()
    db.delete(acc)
    db.commit()


# ---------- categorías ----------
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Category).where(Category.user_id == user.id).order_by(Category.kind, Category.name)).all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    cat = Category(user_id=user.id, **data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# ---------- movimientos ----------
@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: int | None = None,
    category_id: int | None = None,
    kind: str | None = None,
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    q = select(Transaction).where(Transaction.user_id == user.id)
    if date_from:
        q = q.where(Transaction.date >= date_from)
    if date_to:
        q = q.where(Transaction.date <= date_to)
    if account_id:
        q = q.where(Transaction.account_id == account_id)
    if category_id:
        q = q.where(Transaction.category_id == category_id)
    if kind:
        q = q.where(Transaction.kind == kind)
    return db.scalars(q.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit)).all()


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned(db, Account, data.account_id, user)
    if data.category_id:
        owned(db, Category, data.category_id, user)
    tx = Transaction(user_id=user.id, **data.model_dump())
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(owned(db, Transaction, tx_id, user))
    db.commit()


@router.get("/summary/trend")
def trend(months: int = Query(6, ge=1, le=24),
          db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Ingresos y gastos de los últimos N meses (incluye meses vacíos)."""
    today = date.today()
    first = today.year * 12 + today.month - 1 - (months - 1)
    buckets = {}
    for i in range(months):
        y, m = divmod(first + i, 12)
        key = f"{y}-{m + 1:02d}"
        buckets[key] = {"month": key, "income": 0.0, "expense": 0.0}
    start = date(first // 12, first % 12 + 1, 1)
    rows = db.execute(
        select(Transaction.date, Transaction.kind, Transaction.amount)
        .where(Transaction.user_id == user.id, Transaction.date >= start)
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
    base = [Transaction.user_id == user.id, Transaction.date >= start, Transaction.date < end]
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
