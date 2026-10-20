"""Proyección del dinero disponible día a día a partir de los pagos y cobros programados."""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Account
from .queries import account_balances
from .upcoming import upcoming


def cash_today(db: Session, user_id: int) -> Decimal:
    """Dinero propio: cuentas que no son tarjeta de crédito (la deuda de las tarjetas se paga con ese dinero)."""
    moved = account_balances(db, user_id)
    accounts = db.scalars(select(Account).where(Account.user_id == user_id, Account.type != "credit_card"))
    return sum((a.initial_balance + (moved.get(a.id) or 0) for a in accounts), Decimal(0))


def forecast(db: Session, user_id: int, days: int = 60, today: date | None = None) -> dict:
    today = today or clock.today()
    start = cash_today(db, user_id)
    items = upcoming(db, user_id, days, today)

    delta: dict[date, Decimal] = {}
    unknown = overdue = 0
    for i in items:
        if i.get("overdue"):
            overdue += 1  # un cobro vencido puede no llegar nunca: no se cuenta
            continue
        if i["amount"] is None:
            unknown += 1  # se sabe la fecha pero no el monto
            continue
        signed = i["amount"] if i["kind"] == "income" else -i["amount"]
        delta[i["date"]] = delta.get(i["date"], Decimal(0)) + signed

    series, balance = [], start
    lowest = {"date": today, "balance": start}
    for offset in range(days + 1):
        day = today + timedelta(days=offset)
        balance += delta.get(day, Decimal(0))
        series.append({"date": day, "balance": balance})
        if balance < lowest["balance"]:
            lowest = {"date": day, "balance": balance}

    first_negative = next((p["date"] for p in series if p["balance"] < 0), None)
    return {
        "days": days, "start": start, "end": balance, "lowest": lowest,
        "first_negative_date": first_negative, "will_run_short": first_negative is not None,
        "unknown_amounts": unknown, "overdue_excluded": overdue, "series": series,
    }
