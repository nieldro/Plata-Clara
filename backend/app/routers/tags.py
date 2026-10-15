from fastapi import APIRouter, Depends
from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import Tag, Transaction, User, transaction_tags

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


@router.delete("/{tag_id}", status_code=204)
def delete_tag(tag_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Borra la etiqueta de todos los movimientos; los movimientos no se tocan."""
    tag = owned(db, Tag, tag_id, user)
    db.execute(delete(transaction_tags).where(transaction_tags.c.tag_id == tag.id))
    db.delete(tag)
    db.commit()
