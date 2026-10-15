import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Tag, Transaction

MAX_TAGS_PER_TX = 10
MAX_TAG_LEN = 30


def normalize(raw: str) -> str:
    """'#Viaje  Cartagena ' → 'viaje-cartagena' (minúsculas, sin # ni espacios dobles)."""
    name = re.sub(r"\s+", "-", raw.strip().lstrip("#").strip().lower())
    return re.sub(r"-{2,}", "-", name).strip("-")


def clean_names(names: list[str]) -> list[str]:
    seen: list[str] = []
    for raw in names:
        name = normalize(raw)
        if not name:
            continue
        if len(name) > MAX_TAG_LEN:
            raise HTTPException(422, f"La etiqueta «{name[:12]}…» supera los {MAX_TAG_LEN} caracteres")
        if name not in seen:
            seen.append(name)
    if len(seen) > MAX_TAGS_PER_TX:
        raise HTTPException(422, f"Máximo {MAX_TAGS_PER_TX} etiquetas por movimiento")
    return seen


def set_tags(db: Session, user_id: int, tx: Transaction, names: list[str]) -> None:
    """Deja en el movimiento exactamente estas etiquetas, creando las que no existan."""
    wanted = clean_names(names)
    existing = {t.name: t for t in db.scalars(select(Tag).where(Tag.user_id == user_id, Tag.name.in_(wanted or [""])))}
    tags = []
    for name in wanted:
        tag = existing.get(name)
        if not tag:
            tag = Tag(user_id=user_id, name=name)
            db.add(tag)
        tags.append(tag)
    tx.tags = tags
