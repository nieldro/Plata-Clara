"""Genera avisos a partir de los datos del usuario. Cada aviso tiene una `key`
única: correr `generate` muchas veces no repite lo ya avisado."""
import calendar
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Debt, Notification, SavingsGoal, Transaction
from .queries import budget_rows

DUE_WARNING_DAYS = 3
GOAL_WARNING_DAYS = 30


def cop(n) -> str:
    return "$" + f"{float(n):,.0f}".replace(",", ".")


def _add(db: Session, user_id: int, key: str, kind: str, title: str, body: str) -> bool:
    if db.scalar(select(Notification.id).where(Notification.user_id == user_id, Notification.key == key)):
        return False
    db.add(Notification(user_id=user_id, key=key, kind=kind, title=title, body=body))
    db.flush()
    return True


def next_due(day: int, today: date) -> date:
    """Próxima fecha de pago para un día del mes (recorta en meses cortos)."""
    def clamp(y: int, m: int) -> date:
        return date(y, m, min(day, calendar.monthrange(y, m)[1]))
    this = clamp(today.year, today.month)
    if this >= today:
        return this
    return clamp(today.year + (today.month == 12), today.month % 12 + 1)


def _budget_alerts(db: Session, user_id: int, today: date) -> int:
    month = today.strftime("%Y-%m")
    n = 0
    for b in budget_rows(db, user_id, month):
        if b["pct"] >= 100:
            level, title = 100, f"Superaste el presupuesto de {b['category']}"
        elif b["pct"] >= 80:
            level, title = 80, f"Presupuesto de {b['category']} al {int(b['pct'])}%"
        else:
            continue
        body = f"Llevas {cop(b['spent'])} de {cop(b['amount'])} este mes."
        if level == 80:
            body += f" Quedan {cop(b['remaining'])}."
        n += _add(db, user_id, f"budget:{b['category_id']}:{month}:{level}", "budget", title, body)
    return n


def _due_alerts(db: Session, user_id: int, today: date) -> int:
    n = 0
    debts = db.scalars(select(Debt).where(Debt.user_id == user_id, Debt.due_day.is_not(None), Debt.current_balance > 0))
    for d in debts:
        due = next_due(d.due_day, today)
        days = (due - today).days
        if days > DUE_WARNING_DAYS:
            continue
        when = "hoy" if days == 0 else f"en {days} día{'s' if days != 1 else ''}"
        body = f"Vence {when} ({due.isoformat()}). Saldo: {cop(d.current_balance)}."
        if d.monthly_payment:
            body += f" Pago habitual: {cop(d.monthly_payment)}."
        n += _add(db, user_id, f"due:{d.id}:{due.isoformat()}", "due", f"Se acerca el pago de {d.name}", body)
    return n


def _goal_alerts(db: Session, user_id: int, today: date) -> int:
    n = 0
    for g in db.scalars(select(SavingsGoal).where(SavingsGoal.user_id == user_id)):
        if g.current_amount >= g.target_amount:
            continue
        days = (g.target_date - today).days
        missing = cop(g.target_amount - g.current_amount)
        if days < 0:
            n += _add(db, user_id, f"goal:{g.id}:overdue", "goal", f"La meta «{g.name}» ya venció",
                      f"Te faltaron {missing}. Puedes cambiar la fecha o seguir aportando.")
        elif days <= GOAL_WARNING_DAYS:
            n += _add(db, user_id, f"goal:{g.id}:{g.target_date.isoformat()}", "goal",
                      f"Tu meta «{g.name}» vence en {days} día{'s' if days != 1 else ''}",
                      f"Te faltan {missing} para llegar a {cop(g.target_amount)}.")
    return n


def generate(db: Session, user_id: int, today: date | None = None) -> int:
    """Crea los avisos que correspondan hoy. Devuelve cuántos avisos nuevos hubo."""
    today = today or date.today()
    n = _budget_alerts(db, user_id, today) + _due_alerts(db, user_id, today) + _goal_alerts(db, user_id, today)
    db.commit()
    return n


def notify_recurring(db: Session, user_id: int, created: list[tuple]) -> None:
    """Un aviso por cada movimiento recurrente que se acaba de registrar."""
    for rec, tx in created:
        verb = "Se registró el gasto" if tx.kind == "expense" else "Se registró el ingreso"
        _add(db, user_id, f"rec:{tx.id}", "recurring", f"{verb} «{rec.note or 'recurrente'}»",
             f"{cop(tx.amount)} con fecha {tx.date.isoformat()}.")
    db.commit()
