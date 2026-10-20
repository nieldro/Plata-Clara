"""Patrimonio neto al cierre de cada mes: dinero en cuentas menos deudas.

El saldo de las cuentas se reconstruye exacto (saldo inicial + movimientos hasta esa fecha). Las deudas no guardan
historial: se estiman deshaciendo desde hoy los movimientos y pagos posteriores. Los préstamos a personas no cuentan.
"""
import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Account, Debt, DebtPayment, Transaction


def _month_ends(first: date, today: date, months: int) -> list[date]:
    """Último día de cada mes desde `first` hasta hoy (el mes en curso termina hoy), máx. `months`."""
    ends, y, m = [], first.year, first.month
    while (y, m) <= (today.year, today.month):
        last = calendar.monthrange(y, m)[1]
        ends.append(min(date(y, m, last), today))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return ends[-months:]


def net_worth(db: Session, user_id: int, months: int = 12, today: date | None = None) -> list[dict]:
    today = today or clock.today()
    first_tx = db.scalar(select(func.min(Transaction.date)).where(Transaction.user_id == user_id))
    ends = _month_ends(first_tx or today, today, months)

    accounts = db.scalars(select(Account).where(Account.user_id == user_id)).all()
    cash_ids = {a.id for a in accounts if a.type != "credit_card"}
    card_debt = {a.id: a.debt_id for a in accounts if a.type == "credit_card" and a.debt_id}
    initial = sum((a.initial_balance for a in accounts if a.id in cash_ids), Decimal(0))

    cash_flow: list[tuple[date, Decimal]] = []              # (fecha, +ingreso / −gasto) en cuentas propias
    card_flow: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)  # por deuda: (+gasto / −abono)
    for acc_id, when, kind, amount in db.execute(
            select(Transaction.account_id, Transaction.date, Transaction.kind, Transaction.amount)
            .where(Transaction.user_id == user_id)):
        sign = Decimal(1) if kind == "income" else Decimal(-1)
        if acc_id in cash_ids:
            cash_flow.append((when, sign * amount))
        elif acc_id in card_debt:
            card_flow[card_debt[acc_id]].append((when, -sign * amount))

    debts = {d.id: d.current_balance for d in db.scalars(select(Debt).where(Debt.user_id == user_id))}
    pays: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)
    for debt_id, when, principal in db.execute(
            select(DebtPayment.debt_id, DebtPayment.date, DebtPayment.principal).where(DebtPayment.debt_id.in_(debts or [0]))):
        pays[debt_id].append((when, principal))

    out = []
    for end in ends:
        cash = initial + sum((v for d, v in cash_flow if d <= end), Decimal(0))
        debt = Decimal(0)
        for debt_id, current in debts.items():
            after_flow = sum((v for d, v in card_flow.get(debt_id, []) if d > end), Decimal(0))
            after_paid = sum((p for d, p in pays.get(debt_id, []) if d > end), Decimal(0))
            debt += max(current - after_flow + after_paid, Decimal(0))
        out.append({"month": end.strftime("%Y-%m"), "date": end, "cash": cash, "debt": debt,
                    "net_worth": cash - debt, "estimated": end < today})
    return out
