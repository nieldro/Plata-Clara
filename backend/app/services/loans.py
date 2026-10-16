"""Préstamos entre personas y gastos compartidos.

Cuando un préstamo está ligado a una cuenta, genera un movimiento con `loan_id`: cambia el saldo de la
cuenta pero queda fuera de los ingresos/gastos del mes (prestar no es gastar, cobrar no es ganar).
"""
from datetime import date
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Loan, LoanPayment, Transaction
from .ledger import apply_to_card

CENT = Decimal("0.01")


def paid_amounts(db: Session, loan_ids: list[int]) -> dict[int, Decimal]:
    if not loan_ids:
        return {}
    rows = db.execute(select(LoanPayment.loan_id, func.sum(LoanPayment.amount))
                      .where(LoanPayment.loan_id.in_(loan_ids)).group_by(LoanPayment.loan_id)).all()
    return {loan_id: total for loan_id, total in rows}


def loan_out(loan: Loan, paid: Decimal, today: date | None = None) -> dict:
    today = today or clock.today()
    outstanding = loan.amount - paid
    return {
        "id": loan.id, "person": loan.person, "direction": loan.direction, "amount": loan.amount,
        "paid": paid, "outstanding": outstanding, "settled": outstanding <= 0,
        "date": loan.date, "due_date": loan.due_date, "note": loan.note,
        "overdue": bool(loan.due_date and outstanding > 0 and loan.due_date < today),
    }


def money_move(db: Session, user_id: int, account_id: int, kind: str, amount: Decimal, when: date,
               note: str, loan_id: int) -> Transaction:
    tx = Transaction(user_id=user_id, account_id=account_id, kind=kind, amount=amount, date=when,
                     note=note, loan_id=loan_id)
    db.add(tx)
    db.flush()
    apply_to_card(db, account_id, kind, amount, +1)
    return tx


def remove_tx(db: Session, tx: Transaction) -> None:
    apply_to_card(db, tx.account_id, tx.kind, tx.amount, -1)
    db.delete(tx)


def equal_shares(total: Decimal, people: int) -> tuple[Decimal, Decimal]:
    """(parte de cada invitado, lo que queda para mí). Los centavos sobrantes me tocan a mí."""
    each = (total / (people + 1)).quantize(CENT, rounding=ROUND_DOWN)
    return each, total - each * people
