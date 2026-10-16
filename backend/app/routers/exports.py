from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import clock
from ..db import get_db
from ..deps import current_user
from ..models import Account, Category, Transaction, User
from ..services import exporter
from .core import TxFilters, tx_filters

router = APIRouter(prefix="/export", tags=["exportar"])

MEDIA = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def load_rows(db: Session, user: User, f: TxFilters) -> list[exporter.Row]:
    conds = f.conditions(user.id)
    total = db.scalar(select(func.count()).select_from(Transaction).where(*conds))
    if total > exporter.MAX_ROWS:
        raise HTTPException(422, f"Hay {total} movimientos; el máximo por archivo es {exporter.MAX_ROWS}. "
                                 "Acota las fechas o los filtros.")
    accounts = dict(db.execute(select(Account.id, Account.name).where(Account.user_id == user.id)).all())
    cats = dict(db.execute(select(Category.id, Category.name).where(Category.user_id == user.id)).all())
    txs = db.scalars(select(Transaction).where(*conds).order_by(Transaction.date, Transaction.id)).all()
    rows = []
    for t in txs:
        label = "Transferencia" if t.transfer_id else "Préstamo" if t.loan_id else exporter.KIND_LABEL[t.kind]
        sign = 1 if t.kind == "income" else -1
        rows.append(exporter.Row(
            date=t.date, account=accounts.get(t.account_id, ""), category=cats.get(t.category_id, ""),
            kind=t.kind, label=label, amount=sign * t.amount, note=t.note or "",
            tags=", ".join(t.tag_names), receipts=t.attachment_count))
    return rows


@router.get("/transactions")
def export_transactions(format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
                        f: TxFilters = Depends(tx_filters),
                        db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Descarga los movimientos (con los mismos filtros del historial) en CSV o Excel."""
    rows = load_rows(db, user, f)
    body = exporter.to_csv(rows) if format == "csv" else exporter.to_xlsx(rows)
    return Response(body, media_type=MEDIA[format], headers={
        "Content-Disposition": f'attachment; filename="plata-clara-movimientos-{clock.today().isoformat()}.{format}"',
        "Cache-Control": "no-store",
        "X-Row-Count": str(len(rows)),
    })
