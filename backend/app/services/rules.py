"""Categorización automática por palabras clave, sin IA.

Aprende: cada vez que categorizas un movimiento con nota, sus palabras suman un punto hacia esa categoría.
Sugiere: suma los puntos de las palabras de la nota por categoría y propone la ganadora solo si
domina con claridad (CONFIDENCE) — si dudas entre dos, mejor no sugerir nada.
"""
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category, CategoryRule

MIN_TOKEN_LEN = 3
MAX_KEYWORD_LEN = 40
MANUAL_WEIGHT = 1000  # una regla escrita por el usuario pesa más que cualquier aprendizaje
CONFIDENCE = 0.6

STOPWORDS = {
    "compra", "pago", "pagos", "pse", "transferencia", "transf", "tarjeta", "debito", "credito", "abono", "cuota",
    "del", "los", "las", "con", "por", "para", "una", "uno", "sas", "ltda", "cra", "calle", "carrera", "avenida",
    "mes", "nequi", "daviplata", "bancolombia", "davivienda", "bbva", "visa", "mastercard", "cobro", "sede",
    "online", "www", "com", "col", "bogota", "medellin", "cali", "retiro", "cajero", "saldo", "recibo", "factura",
}


def fold(text: str) -> str:
    """'Éxito Cra. 7' → 'exito cra. 7' (minúsculas y sin tildes)."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    out: list[str] = []
    for tok in re.findall(r"[a-z]+", fold(text)):
        if len(tok) >= MIN_TOKEN_LEN and tok not in STOPWORDS and tok not in out:
            out.append(tok[:MAX_KEYWORD_LEN])
    return out


def learn(db: Session, user_id: int, note: str, category_id: int | None) -> None:
    """Suma un punto a cada palabra de la nota hacia la categoría elegida."""
    if not category_id or not note or not note.strip():
        return
    for tok in tokens(note):
        rule = db.scalar(select(CategoryRule).where(
            CategoryRule.user_id == user_id, CategoryRule.keyword == tok, CategoryRule.category_id == category_id))
        if rule:
            rule.hits += 1
        else:
            db.add(CategoryRule(user_id=user_id, keyword=tok, category_id=category_id))
    db.flush()


def suggest(db: Session, user_id: int, text: str, kind: str | None = None) -> dict | None:
    """Categoría sugerida para un texto, o None si no hay evidencia suficiente."""
    toks = tokens(text or "")
    if not toks:
        return None
    rows = db.execute(
        select(CategoryRule, Category)
        .join(Category, Category.id == CategoryRule.category_id)
        .where(CategoryRule.user_id == user_id, CategoryRule.keyword.in_(toks))
    ).all()
    score: dict[int, float] = {}
    matched: dict[int, set[str]] = {}
    for rule, cat in rows:
        if kind and cat.kind != kind:
            continue
        score[cat.id] = score.get(cat.id, 0) + (MANUAL_WEIGHT if rule.manual else rule.hits)
        matched.setdefault(cat.id, set()).add(rule.keyword)
    if not score:
        return None
    total = sum(score.values())
    best = max(score, key=score.get)
    confidence = score[best] / total
    if confidence < CONFIDENCE:
        return None
    return {"category_id": best, "confidence": round(confidence, 2), "matched": sorted(matched[best])}
