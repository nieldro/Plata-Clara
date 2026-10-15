import calendar
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Recurring, Transaction
from .ledger import apply_to_card

MAX_CATCHUP = 60  # tope de repeticiones atrasadas por corrida


def add_months(d: date, months: int, anchor_day: int) -> date:
    """Suma meses conservando el día original (31 → 28/29/30 en meses cortos)."""
    year, month0 = divmod(d.year * 12 + d.month - 1 + months, 12)
    month = month0 + 1
    return date(year, month, min(anchor_day, calendar.monthrange(year, month)[1]))


def advance(rec: Recurring) -> date:
    if rec.frequency == "weekly":
        return rec.next_date + timedelta(days=7)
    if rec.frequency == "biweekly":
        return rec.next_date + timedelta(days=14)
    return add_months(rec.next_date, 1, rec.anchor_day)


def run_due(db: Session, user_id: int, today: date | None = None) -> list[tuple[Recurring, Transaction]]:
    """Registra los movimientos recurrentes vencidos (incluye los atrasados).

    Es idempotente: tras correr, `next_date` queda en el futuro y una segunda
    llamada no crea nada.
    """
    today = today or date.today()
    created: list[tuple[Recurring, Transaction]] = []
    due = db.scalars(
        select(Recurring).where(Recurring.user_id == user_id, Recurring.active.is_(True), Recurring.next_date <= today)
    ).all()
    for rec in due:
        steps = 0
        while rec.next_date <= today and steps < MAX_CATCHUP:
            tx = Transaction(
                user_id=user_id, account_id=rec.account_id, category_id=rec.category_id, kind=rec.kind,
                amount=rec.amount, date=rec.next_date, note=rec.note or "Recurrente",
            )
            db.add(tx)
            db.flush()
            apply_to_card(db, tx.account_id, tx.kind, tx.amount, +1)
            created.append((rec, tx))
            rec.next_date = advance(rec)
            steps += 1
    db.commit()
    return created
