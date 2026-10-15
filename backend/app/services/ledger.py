"""Efectos de un movimiento sobre otras tablas (tarjetas de crédito)."""
from decimal import Decimal

from sqlalchemy.orm import Session

from ..models import Account, Debt


def apply_to_card(db: Session, account_id: int, kind: str, amount: Decimal, sign: int) -> None:
    """Refleja un movimiento en la deuda de la tarjeta (sign=+1 al crearlo, -1 al borrarlo).

    Un gasto sube la deuda; un ingreso (abono/pago) la baja. Nunca queda negativa.
    """
    acc = db.get(Account, account_id)
    if not acc or not acc.debt_id:
        return
    debt = db.get(Debt, acc.debt_id)
    if not debt:
        return
    delta = amount if kind == "expense" else -amount
    debt.current_balance = max(debt.current_balance + delta * sign, Decimal(0))
