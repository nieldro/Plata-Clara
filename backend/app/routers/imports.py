from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, limit_heavy, owned
from ..models import Account, Category, Transaction, User
from ..schemas import ImportCommitIn
from ..services import importer
from ..services.ledger import apply_to_card
from ..services.rules import fold, learn, suggest
from ..services.tags import set_tags
from ..services.uploads import read_limited

router = APIRouter(prefix="/imports", tags=["importar"])

CHUNK = 400  # SQLite limita las variables por consulta


def _chunks(items: list, size: int = CHUNK):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _existing_hashes(db: Session, user_id: int, hashes: list[str]) -> set[str]:
    found: set[str] = set()
    for part in _chunks(hashes):
        found.update(db.scalars(select(Transaction.import_hash).where(
            Transaction.user_id == user_id, Transaction.import_hash.in_(part))))
    return found


def _mark_duplicates(db: Session, user_id: int, account_id: int, rows: list[importer.ParsedRow]) -> dict[int, str]:
    """line → 'exact' (ya importado antes) | 'possible' (misma fecha, monto y tipo que uno existente)."""
    good = [r for r in rows if not r.error]
    if not good:
        return {}
    exact = _existing_hashes(db, user_id, [r.import_hash for r in good])
    lo, hi = min(r.date for r in good), max(r.date for r in good)
    manual: dict[tuple, int] = defaultdict(int)
    for d, amount, kind in db.execute(
        select(Transaction.date, Transaction.amount, Transaction.kind)
        .where(Transaction.user_id == user_id, Transaction.account_id == account_id,
               Transaction.transfer_id.is_(None), Transaction.import_hash.is_(None),
               Transaction.date >= lo, Transaction.date <= hi)
    ):
        manual[(d, Decimal(amount).quantize(Decimal("0.01")), kind)] += 1
    result: dict[int, str] = {}
    for r in good:
        if r.import_hash in exact:
            result[r.line] = "exact"
            continue
        key = (r.date, r.amount, r.kind)
        if manual.get(key):  # cada movimiento manual se «consume» una sola vez
            manual[key] -= 1
            result[r.line] = "possible"
    return result


def _mapping_from_form(values: dict[str, int | None], detected: dict[str, int | None]) -> dict[str, int | None]:
    if any(v is not None for v in values.values()):
        return {k: (v if v is not None and v >= 0 else None) for k, v in values.items()}
    return detected


@router.post("/preview", dependencies=[Depends(limit_heavy)])
async def preview(
    file: UploadFile = File(...),
    account_id: int = Form(...),
    date_col: int | None = Form(None),
    description_col: int | None = Form(None),
    amount_col: int | None = Form(None),
    debit_col: int | None = Form(None),
    credit_col: int | None = Form(None),
    date_order: str = Form("dmy", pattern="^(dmy|mdy)$"),
    invert: bool = Form(False),
    has_header: bool | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Lee el extracto y muestra qué movimientos crearía. No guarda nada."""
    owned(db, Account, account_id, user)
    data = await read_limited(file)
    try:
        table = importer.read_table(file.filename or "", data)
    except importer.ImportError_ as e:
        raise HTTPException(422, str(e)) from e

    header_index = importer.find_header(table)
    if header_index is None and has_header:
        header_index = 0
    header = table[header_index] if header_index is not None else []
    width = max(len(r) for r in table[:50])
    columns = [header[i] if i < len(header) and header[i] else f"Columna {i + 1}" for i in range(width)]
    detected = importer.detect_mapping(header) if header else {k: None for k in importer.FIELD_ORDER}
    mapping = _mapping_from_form(
        {"date": date_col, "description": description_col, "amount": amount_col, "debit": debit_col, "credit": credit_col},
        detected,
    )
    start = 0 if header_index is None else header_index + 1
    base = {"columns": columns, "header_row": header_index, "mapping": mapping, "sample": table[start:start + 5]}

    ready = mapping["date"] is not None and any(mapping[k] is not None for k in ("amount", "debit", "credit"))
    if not ready:
        return {**base, "needs_mapping": True, "rows": [], "stats": None}

    try:
        parsed = importer.build_rows(table, mapping, header_index, account_id=account_id,
                                     date_order=date_order, invert=invert)
    except importer.ImportError_ as e:
        raise HTTPException(422, str(e)) from e

    dups = _mark_duplicates(db, user.id, account_id, parsed)
    cache: dict[tuple, dict | None] = {}
    out = []
    for r in parsed:
        item = {"line": r.line, "date": r.date, "description": r.description, "amount": r.amount, "kind": r.kind,
                "error": r.error, "import_hash": r.import_hash, "duplicate": dups.get(r.line), "category_id": None}
        if not r.error:
            key = (fold(r.description), r.kind)
            if key not in cache:
                cache[key] = suggest(db, user.id, r.description, r.kind)
            if cache[key]:
                item["category_id"] = cache[key]["category_id"]
        out.append(item)

    ok = [r for r in out if not r["error"]]
    new = [r for r in ok if not r["duplicate"]]
    stats = {
        "total": len(out), "valid": len(ok), "errors": len(out) - len(ok),
        "exact_duplicates": sum(r["duplicate"] == "exact" for r in ok),
        "possible_duplicates": sum(r["duplicate"] == "possible" for r in ok),
        "new_income": sum((r["amount"] for r in new if r["kind"] == "income"), Decimal(0)),
        "new_expense": sum((r["amount"] for r in new if r["kind"] == "expense"), Decimal(0)),
        "from": min((r["date"] for r in ok), default=None), "to": max((r["date"] for r in ok), default=None),
    }
    return {**base, "needs_mapping": False, "rows": out, "stats": stats}


@router.post("/commit", status_code=201)
def commit(data: ImportCommitIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Guarda las filas elegidas. Las que ya se importaron antes (misma huella) se omiten."""
    owned(db, Account, data.account_id, user)
    category_ids = {r.category_id for r in data.rows if r.category_id}
    if category_ids:
        found = set(db.scalars(select(Category.id).where(Category.user_id == user.id, Category.id.in_(category_ids))))
        if found != category_ids:
            raise HTTPException(404, "Una de las categorías no existe")

    existing = _existing_hashes(db, user.id, [r.import_hash for r in data.rows])
    created = skipped = 0
    seen: set[str] = set()
    for r in data.rows:
        if r.import_hash in existing or r.import_hash in seen:
            skipped += 1
            continue
        seen.add(r.import_hash)
        tx = Transaction(user_id=user.id, account_id=data.account_id, category_id=r.category_id, kind=r.kind,
                         amount=r.amount, date=r.date, note=r.description, import_hash=r.import_hash)
        db.add(tx)
        db.flush()
        set_tags(db, user.id, tx, r.tags)
        learn(db, user.id, r.description, r.category_id)
        apply_to_card(db, tx.account_id, tx.kind, tx.amount, +1)
        created += 1
    db.commit()
    return {"created": created, "skipped": skipped}
