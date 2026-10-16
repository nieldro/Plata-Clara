"""Consultas reutilizables (resumen mensual, presupuestos) usadas por varios routers."""
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Budget, Category, Transaction


def current_month() -> str:
    return clock.today().strftime("%Y-%m")


def month_bounds(month: str) -> tuple[date, date]:
    """Primer día del mes y primer día del mes siguiente."""
    year, mon = int(month[:4]), int(month[5:])
    return date(year, mon, 1), date(year + (mon == 12), mon % 12 + 1, 1)


def prev_month(month: str) -> str:
    year, mon = int(month[:4]), int(month[5:])
    return f"{year - (mon == 1)}-{(mon - 2) % 12 + 1:02d}"


def spent_by_category(db: Session, user_id: int, start: date, end: date) -> dict[int | None, Decimal]:
    rows = db.execute(
        select(Transaction.category_id, func.sum(Transaction.amount))
        .where(Transaction.user_id == user_id, Transaction.kind == "expense",
               Transaction.transfer_id.is_(None), Transaction.loan_id.is_(None),
               Transaction.date >= start, Transaction.date < end)
        .group_by(Transaction.category_id)
    ).all()
    return {cat: total for cat, total in rows}


def month_totals(db: Session, user_id: int, month: str) -> tuple[Decimal, Decimal]:
    """(ingresos, gastos) del mes."""
    start, end = month_bounds(month)
    totals = dict(db.execute(
        select(Transaction.kind, func.sum(Transaction.amount))
        .where(Transaction.user_id == user_id, Transaction.transfer_id.is_(None), Transaction.loan_id.is_(None),
               Transaction.date >= start, Transaction.date < end)
        .group_by(Transaction.kind)
    ).all())
    return totals.get("income") or Decimal(0), totals.get("expense") or Decimal(0)


def account_balances(db: Session, user_id: int) -> dict[int, Decimal]:
    """Suma de movimientos por cuenta (ingresos − gastos), sin el saldo inicial."""
    signed = case((Transaction.kind == "income", Transaction.amount), else_=-Transaction.amount)
    rows = db.execute(
        select(Transaction.account_id, func.sum(signed))
        .where(Transaction.user_id == user_id)
        .group_by(Transaction.account_id)
    ).all()
    return {acc: total for acc, total in rows}


def budget_rows(db: Session, user_id: int, month: str) -> list[dict]:
    """Cada presupuesto con lo gastado en el mes, lo que queda y el % usado."""
    start, end = month_bounds(month)
    spent = spent_by_category(db, user_id, start, end)
    rows = db.execute(
        select(Budget, Category.name)
        .join(Category, Category.id == Budget.category_id)
        .where(Budget.user_id == user_id)
        .order_by(Category.name)
    ).all()
    out = []
    for budget, name in rows:
        used = spent.get(budget.category_id) or Decimal(0)
        out.append({
            "category_id": budget.category_id,
            "category": name,
            "amount": budget.amount,
            "spent": used,
            "remaining": budget.amount - used,
            "pct": round(float(used / budget.amount * 100), 1),
        })
    return out
