from collections import defaultdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..db import get_db
from ..deps import current_user
from ..institutions import INSTITUTIONS
from ..models import Account, User
from ..services import quickadd
from ..services.rules import fold, suggest

router = APIRouter(prefix="/quick-add", tags=["captura rápida"])
INSTITUTION_NAMES = {i["slug"]: i["name"] for i in INSTITUTIONS}


class QuickAddIn(BaseModel):
    text: str = Field(max_length=300)


def _account_index(accounts: list[Account]) -> tuple[dict[str, int], list[str]]:
    """Nombres con los que se puede mencionar una cuenta («nequi», «ahorros nómina»…) → id.
    Un nombre que pertenece a varias cuentas es ambiguo: no se usa y se avisa."""
    owners: dict[str, set[int]] = defaultdict(set)
    for a in accounts:
        names = {a.name, INSTITUTION_NAMES.get(a.institution or "", ""), a.institution_name or ""}
        for n in names:
            key = fold(n).strip()
            if len(key) >= 3:
                owners[key].add(a.id)
    unique = {k: next(iter(v)) for k, v in owners.items() if len(v) == 1}
    ambiguous = sorted(k for k, v in owners.items() if len(v) > 1)
    return unique, ambiguous


@router.post("/parse")
def parse_text(data: QuickAddIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Convierte «café 4.500 ayer con nequi #trabajo» en un movimiento propuesto. No guarda nada."""
    accounts = db.scalars(select(Account).where(Account.user_id == user.id).order_by(Account.id)).all()
    index, ambiguous = _account_index(accounts)
    parsed = quickadd.parse(data.text, clock.today(), index)

    account = next((a for a in accounts if a.id == index.get(parsed.account_hint or "")), None)
    warnings = list(parsed.warnings)
    low = fold(data.text)
    for name in ambiguous:
        if f" {name}" in f" {low}" and name in low:
            warnings.append(f"Tienes varias cuentas «{name}»: elige cuál")
    if account is None and len(accounts) == 1:
        account = accounts[0]  # con una sola cuenta no hay que adivinar

    suggestion = suggest(db, user.id, parsed.note, parsed.kind) if parsed.note else None
    return {
        "ready": parsed.amount is not None,
        "amount": parsed.amount,
        "kind": parsed.kind,
        "date": parsed.when,
        "note": parsed.note,
        "tags": parsed.tags,
        "account_id": account.id if account else None,
        "account_name": account.name if account else None,
        "category_id": suggestion["category_id"] if suggestion else None,
        "category_confidence": suggestion["confidence"] if suggestion else None,
        "warnings": warnings,
    }
