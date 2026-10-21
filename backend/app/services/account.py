"""Exportar y borrar todos los datos de un usuario."""
import json
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..models import (Account, Attachment, Budget, Category, CategoryRule, Debt, DebtPayment, Loan, LoanPayment,
                      Notification, Recurring, SavedFilter, SavingsContribution, SavingsGoal, Tag, Transaction, User,
                      transaction_tags)
from . import uploads

# (clave en el archivo, modelo): tablas que pertenecen directamente al usuario por user_id
OWNED = [("accounts", Account), ("categories", Category), ("transactions", Transaction), ("budgets", Budget),
         ("recurring", Recurring), ("debts", Debt), ("savings_goals", SavingsGoal), ("loans", Loan),
         ("tags", Tag), ("category_rules", CategoryRule), ("notifications", Notification),
         ("attachments", Attachment), ("saved_filters", SavedFilter)]
# Al crear una tabla con columna user_id hay que agregarla aquí (exportar) y en delete_user (borrar la cuenta);
# tests/test_account.py::test_every_user_table_is_exported_and_deleted falla si se olvida.


def _plain(value):
    if isinstance(value, Decimal):
        return str(value)  # texto: sin perder centavos por pasar por float
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _row(obj) -> dict:
    return {c.name: _plain(getattr(obj, c.name)) for c in obj.__table__.columns}


def export_data(db: Session, user: User) -> str:
    """Todos los datos del usuario en JSON (sin contraseña ni los archivos de recibos, solo su ficha)."""
    out: dict = {
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "app": "Plata Clara",
        "user": {"id": user.id, "email": user.email, "name": user.name, "created_at": _plain(user.created_at)},
    }
    for key, model in OWNED:
        out[key] = [_row(o) for o in db.scalars(select(model).where(model.user_id == user.id).order_by(model.id))]
    tx_ids = [t["id"] for t in out["transactions"]]
    tag_names = {t["id"]: t["name"] for t in out["tags"]}
    links: dict[int, list[str]] = {}
    for part in range(0, len(tx_ids), 400):
        for tx_id, tag_id in db.execute(select(transaction_tags).where(
                transaction_tags.c.transaction_id.in_(tx_ids[part:part + 400]))):
            links.setdefault(tx_id, []).append(tag_names.get(tag_id, ""))
    for t in out["transactions"]:
        t["tags"] = sorted(links.get(t["id"], []))
    debt_ids = [d["id"] for d in out["debts"]]
    goal_ids = [g["id"] for g in out["savings_goals"]]
    loan_ids = [l["id"] for l in out["loans"]]
    out["debt_payments"] = [_row(o) for o in db.scalars(select(DebtPayment).where(DebtPayment.debt_id.in_(debt_ids or [0])))]
    out["savings_contributions"] = [_row(o) for o in db.scalars(
        select(SavingsContribution).where(SavingsContribution.goal_id.in_(goal_ids or [0])))]
    out["loan_payments"] = [_row(o) for o in db.scalars(select(LoanPayment).where(LoanPayment.loan_id.in_(loan_ids or [0])))]
    for a in out["attachments"]:
        a.pop("stored_name", None)  # nombre interno en disco: no le sirve al usuario
    return json.dumps(out, ensure_ascii=False, indent=2)


def delete_user(db: Session, user: User) -> None:
    """Borra la cuenta y todo lo suyo, en el orden que exigen las llaves foráneas, y sus archivos del disco."""
    uid = user.id
    stored = list(db.scalars(select(Attachment.stored_name).where(Attachment.user_id == uid)))
    tx_ids = list(db.scalars(select(Transaction.id).where(Transaction.user_id == uid)))
    loan_ids = list(db.scalars(select(Loan.id).where(Loan.user_id == uid)))
    debt_ids = list(db.scalars(select(Debt.id).where(Debt.user_id == uid)))
    goal_ids = list(db.scalars(select(SavingsGoal.id).where(SavingsGoal.user_id == uid)))

    def chunks(ids):
        for i in range(0, len(ids), 400):
            yield ids[i:i + 400]

    for c in chunks(loan_ids):
        db.execute(delete(LoanPayment).where(LoanPayment.loan_id.in_(c)))
    for c in chunks(tx_ids):
        db.execute(delete(transaction_tags).where(transaction_tags.c.transaction_id.in_(c)))
    db.execute(delete(Attachment).where(Attachment.user_id == uid))
    db.execute(delete(Transaction).where(Transaction.user_id == uid))
    db.execute(delete(Loan).where(Loan.user_id == uid))
    db.execute(delete(Recurring).where(Recurring.user_id == uid))
    db.execute(delete(Budget).where(Budget.user_id == uid))
    db.execute(delete(CategoryRule).where(CategoryRule.user_id == uid))
    db.execute(delete(Category).where(Category.user_id == uid))
    db.execute(delete(Tag).where(Tag.user_id == uid))
    for c in chunks(debt_ids):
        db.execute(delete(DebtPayment).where(DebtPayment.debt_id.in_(c)))
    db.execute(update(Account).where(Account.user_id == uid).values(debt_id=None))
    db.execute(delete(Account).where(Account.user_id == uid))
    db.execute(delete(Debt).where(Debt.user_id == uid))
    for c in chunks(goal_ids):
        db.execute(delete(SavingsContribution).where(SavingsContribution.goal_id.in_(c)))
    db.execute(delete(SavingsGoal).where(SavingsGoal.user_id == uid))
    db.execute(delete(Notification).where(Notification.user_id == uid))
    db.execute(delete(SavedFilter).where(SavedFilter.user_id == uid))
    db.execute(delete(User).where(User.id == uid))
    db.commit()
    for name in stored:  # los archivos se borran después de confirmar la base
        uploads.remove(uid, name)
