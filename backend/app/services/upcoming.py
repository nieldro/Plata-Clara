"""Lo que viene: recurrentes, vencimientos de tarjetas y créditos, y préstamos con fecha límite."""
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Category, Debt, Loan, Recurring
from .loans import paid_amounts
from .notifications import next_due
from .recurring import add_months, advance

MAX_ITEMS = 300


def _occurrences(rec: Recurring, start: date, end: date) -> list[date]:
    """Fechas en que se registraría un recurrente dentro de [start, end] (sin tocar la base)."""
    cur = SimpleNamespace(next_date=rec.next_date, frequency=rec.frequency, anchor_day=rec.anchor_day)
    out: list[date] = []
    while cur.next_date <= end and len(out) < MAX_ITEMS:
        if cur.next_date >= start:
            out.append(cur.next_date)
        cur.next_date = advance(cur)
    return out


def _item(when: date, today: date, kind: str, title: str, amount: Decimal | None, source: str, **extra) -> dict:
    return {"date": when, "days": (when - today).days, "kind": kind, "title": title, "amount": amount,
            "source": source, **extra}


def upcoming(db: Session, user_id: int, days: int = 30, today: date | None = None) -> list[dict]:
    """Movimientos esperados en los próximos `days` días, ordenados por fecha. Los préstamos vencidos van primero."""
    today = today or clock.today()
    end = today + timedelta(days=days)
    items: list[dict] = []

    cats = dict(db.execute(select(Category.id, Category.name).where(Category.user_id == user_id)).all())
    for rec in db.scalars(select(Recurring).where(Recurring.user_id == user_id, Recurring.active.is_(True))):
        title = rec.note or cats.get(rec.category_id) or "Recurrente"
        for when in _occurrences(rec, today, end):
            items.append(_item(when, today, rec.kind, title, rec.amount, "recurring", id=rec.id))

    for debt in db.scalars(select(Debt).where(Debt.user_id == user_id, Debt.due_day.is_not(None), Debt.current_balance > 0)):
        when = next_due(debt.due_day, today)
        while when <= end and len(items) < MAX_ITEMS:
            items.append(_item(when, today, "expense", f"Pago de {debt.name}", debt.monthly_payment, "debt", id=debt.id))
            when = add_months(when, 1, debt.due_day)

    loans = list(db.scalars(select(Loan).where(Loan.user_id == user_id, Loan.due_date.is_not(None), Loan.due_date <= end)))
    paid = paid_amounts(db, [loan.id for loan in loans])
    for loan in loans:
        left = loan.amount - (paid.get(loan.id) or 0)
        if left <= 0:
            continue
        lent = loan.direction == "lent"
        title = f"{loan.person} te debe" if lent else f"Le debes a {loan.person}"
        items.append(_item(loan.due_date, today, "income" if lent else "expense", title, left, "loan",
                           id=loan.id, overdue=loan.due_date < today))

    items.sort(key=lambda i: (i["date"], i["title"]))
    return items[:MAX_ITEMS]
