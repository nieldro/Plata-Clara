from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, delete, func, insert, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import Tag, Transaction, User, transaction_tags
from ..schemas import TagRename
from ..services.tags import MAX_TAG_LEN, normalize

router = APIRouter(prefix="/tags", tags=["etiquetas"])


@router.get("")
def list_tags(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Cada etiqueta con cuántos movimientos tiene y cuánto sumaron sus gastos e ingresos."""
    income = func.coalesce(func.sum(case((Transaction.kind == "income", Transaction.amount), else_=0)), 0)
    expense = func.coalesce(func.sum(case((Transaction.kind == "expense", Transaction.amount), else_=0)), 0)
    rows = db.execute(
        select(Tag.id, Tag.name, func.count(Transaction.id), income, expense)
        .select_from(Tag)
        .outerjoin(transaction_tags, transaction_tags.c.tag_id == Tag.id)
        .outerjoin(Transaction, Transaction.id == transaction_tags.c.transaction_id)
        .where(Tag.user_id == user.id)
        .group_by(Tag.id, Tag.name)
        .order_by(Tag.name)
    ).all()
    return [{"id": i, "name": n, "count": c, "income": inc, "expense": exp} for i, n, c, inc, exp in rows]


@router.patch("/{tag_id}")
def rename_tag(tag_id: int, data: TagRename, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Renombra una etiqueta. Si ya existe otra con ese nombre, se **fusionan**: los movimientos pasan a la existente."""
    tag = owned(db, Tag, tag_id, user)
    name = normalize(data.name)
    if not name:
        raise HTTPException(422, "Escribe el nombre de la etiqueta")
    if len(name) > MAX_TAG_LEN:
        raise HTTPException(422, f"El nombre no puede superar los {MAX_TAG_LEN} caracteres")
    if name == tag.name:
        return {"id": tag.id, "name": tag.name, "merged": False, "moved": 0}

    target = db.scalar(select(Tag).where(Tag.user_id == user.id, Tag.name == name))
    if target is None:
        tag.name = name
        db.commit()
        return {"id": tag.id, "name": name, "merged": False, "moved": 0}

    # fusión: lo que ya tenía las dos etiquetas no se duplica
    has_target = set(db.scalars(select(transaction_tags.c.transaction_id).where(transaction_tags.c.tag_id == target.id)))
    moving = [t for t in db.scalars(select(transaction_tags.c.transaction_id).where(transaction_tags.c.tag_id == tag.id))
              if t not in has_target]
    if moving:
        db.execute(insert(transaction_tags), [{"transaction_id": t, "tag_id": target.id} for t in moving])
    db.execute(delete(transaction_tags).where(transaction_tags.c.tag_id == tag.id))
    db.delete(tag)
    db.commit()
    return {"id": target.id, "name": target.name, "merged": True, "moved": len(moving)}


@router.delete("/{tag_id}", status_code=204)
def delete_tag(tag_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Borra la etiqueta de todos los movimientos; los movimientos no se tocan."""
    tag = owned(db, Tag, tag_id, user)
    db.execute(delete(transaction_tags).where(transaction_tags.c.tag_id == tag.id))
    db.delete(tag)
    db.commit()
