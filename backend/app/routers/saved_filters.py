import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import SavedFilter, User
from ..schemas import SavedFilterIn

router = APIRouter(prefix="/saved-filters", tags=["vistas guardadas"])

MAX_PER_USER = 30


def _out(f: SavedFilter) -> dict:
    try:
        params = json.loads(f.params)
    except ValueError:
        params = {}
    return {"id": f.id, "name": f.name, "params": params}


@router.get("")
def list_filters(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(SavedFilter).where(SavedFilter.user_id == user.id).order_by(func.lower(SavedFilter.name)))
    return [_out(f) for f in rows]


@router.post("", status_code=201)
def save_filter(data: SavedFilterIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Guarda (o reemplaza, si el nombre ya existe) una combinación de filtros del historial."""
    existing = db.scalar(select(SavedFilter).where(SavedFilter.user_id == user.id,
                                                   func.lower(SavedFilter.name) == data.name.lower()))
    if existing:
        existing.params = json.dumps(data.params, ensure_ascii=False)
        db.commit()
        return _out(existing)
    if db.scalar(select(func.count()).select_from(SavedFilter).where(SavedFilter.user_id == user.id)) >= MAX_PER_USER:
        raise HTTPException(422, f"Puedes guardar hasta {MAX_PER_USER} vistas: borra alguna para crear otra")
    f = SavedFilter(user_id=user.id, name=data.name, params=json.dumps(data.params, ensure_ascii=False))
    db.add(f)
    db.commit()
    db.refresh(f)
    return _out(f)


@router.delete("/{filter_id}", status_code=204)
def delete_filter(filter_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(owned(db, SavedFilter, filter_id, user))
    db.commit()
