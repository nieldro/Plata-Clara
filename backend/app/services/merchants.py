"""Gasto agrupado por comercio, tomado de la nota: «Éxito Calle 80» y «EXITO chapinero» son el mismo comercio."""
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Transaction
from .queries import month_bounds
from .rules import fold, tokens

NO_NOTE = "(sin nota)"


def merchant_key(note: str | None) -> str:
    """Primera palabra con significado de la nota (sin tildes ni mayúsculas); «» si no hay."""
    toks = tokens(note or "")
    return toks[0] if toks else ""


def _display(variants: dict[str, int], key: str) -> str:
    """El nombre más usado tal como lo escribió el usuario, o la clave con mayúscula inicial."""
    if not key:
        return NO_NOTE
    best = max(variants.items(), key=lambda kv: kv[1])[0] if variants else key
    # la palabra de la nota que da origen a la clave (comparando sin tildes), con su ortografía original
    word = next((w for w in best.split() if fold(w).strip(".,;:") == key), key)
    return word.strip(".,;:").capitalize()


def top_merchants(db: Session, user_id: int, month: str, limit: int = 10) -> dict:
    start, end = month_bounds(month)
    rows = db.execute(
        select(Transaction.note, Transaction.amount)
        .where(Transaction.user_id == user_id, Transaction.kind == "expense", Transaction.transfer_id.is_(None),
               Transaction.loan_id.is_(None), Transaction.date >= start, Transaction.date < end)
    ).all()
    totals: dict[str, Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    variants: dict[str, dict[str, int]] = defaultdict(dict)
    for note, amount in rows:
        key = merchant_key(note)
        totals[key] += amount
        counts[key] += 1
        text = (note or "").strip()
        if text:
            variants[key][text] = variants[key].get(text, 0) + 1
    grand = sum(totals.values(), Decimal(0))
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    items = [{"name": _display(variants[k], k), "key": k, "count": counts[k], "total": t,
              "pct": round(float(t / grand * 100), 1) if grand else 0.0} for k, t in ranked[:limit]]
    return {"month": month, "total_expense": grand, "merchants": len(totals), "items": items}
