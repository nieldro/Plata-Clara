from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import Notification, User
from ..schemas import NotificationOut, NotificationPrefsIn
from ..services import notifications as svc
from ..services.notifications import KINDS, muted_kinds

router = APIRouter(prefix="/notifications", tags=["notificaciones"])


def _payload(db: Session, user_id: int, new: int = 0) -> dict:
    muted = muted_kinds(db, user_id)  # los tipos silenciados tampoco se muestran ni cuentan como no leídos
    visible = [Notification.user_id == user_id, Notification.kind.not_in(muted)] if muted else [Notification.user_id == user_id]
    items = db.scalars(select(Notification).where(*visible).order_by(Notification.id.desc()).limit(50)).all()
    unread = db.scalar(select(func.count()).select_from(Notification).where(*visible, Notification.read.is_(False)))
    return {"unread": unread, "new": new, "items": [NotificationOut.model_validate(i) for i in items]}


@router.get("/preferences")
def get_preferences(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Qué tipos de aviso quieres recibir."""
    muted = muted_kinds(db, user.id)
    return {"kinds": [{"kind": k, "label": label, "enabled": k not in muted} for k, label in KINDS.items()]}


@router.put("/preferences")
def set_preferences(data: NotificationPrefsIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Define los tipos de aviso que quieres silenciar (lista vacía = recibirlos todos)."""
    user.notif_muted = ",".join(sorted(set(data.muted)))
    db.commit()
    return get_preferences(db, user)


@router.get("")
def list_notifications(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _payload(db, user.id)


@router.post("/refresh")
def refresh(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Revisa presupuestos, vencimientos y metas, y devuelve la lista actualizada."""
    return _payload(db, user.id, svc.generate(db, user.id))


@router.post("/read-all", status_code=204)
def read_all(db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.execute(update(Notification).where(Notification.user_id == user.id).values(read=True))
    db.commit()


@router.post("/{notification_id}/read", status_code=204)
def read_one(notification_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned(db, Notification, notification_id, user).read = True
    db.commit()


@router.delete("/{notification_id}", status_code=204)
def delete_one(notification_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(owned(db, Notification, notification_id, user))
    db.commit()
