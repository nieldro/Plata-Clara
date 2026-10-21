from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import Account, Category, Recurring, User
from ..schemas import RecurringIn, RecurringOut
from ..services import recurring as svc
from ..services.recurring_detect import detect
from ..services.notifications import notify_recurring

router = APIRouter(prefix="/recurring", tags=["recurrentes"])


@router.get("", response_model=list[RecurringOut])
def list_recurring(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Recurring).where(Recurring.user_id == user.id).order_by(Recurring.next_date)).all()


@router.get("/suggestions")
def suggestions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Gastos o ingresos que parecen repetirse (3 veces o más, a intervalos regulares) y aún no son recurrentes."""
    return detect(db, user.id)


@router.post("", response_model=RecurringOut, status_code=201)
def create_recurring(data: RecurringIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned(db, Account, data.account_id, user)
    if data.category_id:
        owned(db, Category, data.category_id, user)
    rec = Recurring(
        user_id=user.id, account_id=data.account_id, category_id=data.category_id, kind=data.kind,
        amount=data.amount, note=data.note, frequency=data.frequency,
        anchor_day=data.start_date.day, next_date=data.start_date,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.post("/{rec_id}/toggle", response_model=RecurringOut)
def toggle(rec_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    rec = owned(db, Recurring, rec_id, user)
    rec.active = not rec.active
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/{rec_id}", status_code=204)
def delete_recurring(rec_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(owned(db, Recurring, rec_id, user))
    db.commit()


@router.post("/run")
def run(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Registra los movimientos recurrentes que ya vencieron. Se puede llamar las veces que sea."""
    created = svc.run_due(db, user.id)
    notify_recurring(db, user.id, created)
    return {"created": len(created), "transaction_ids": [tx.id for _, tx in created]}
