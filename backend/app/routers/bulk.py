from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import Category, Transaction, User
from ..schemas import BulkIn
from ..services.ledger import apply_to_card
from ..services.rules import learn
from ..services.tags import MAX_TAGS_PER_TX, normalize, set_tags
from ..services.uploads import purge_files_for

router = APIRouter(prefix="/transactions/bulk", tags=["movimientos"])

LOCKED = "transferencia o préstamo: se gestiona desde su propia pantalla"


@router.post("")
def bulk(data: BulkIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Borra, recategoriza o etiqueta varios movimientos a la vez.

    Lo que no se puede tocar (transferencias, préstamos, tipo de categoría distinto…) se omite y se explica por qué;
    lo demás se aplica. Nunca afecta movimientos de otra persona."""
    found = {t.id: t for t in db.scalars(
        select(Transaction).where(Transaction.user_id == user.id, Transaction.id.in_(data.ids)))}
    not_found = [i for i in data.ids if i not in found]
    category = owned(db, Category, data.category_id, user) if data.action == "set_category" and data.category_id else None
    tag = normalize(data.tag or "")

    affected, skipped = 0, []
    for tx_id in data.ids:
        tx = found.get(tx_id)
        if tx is None:
            continue
        if tx.transfer_id or tx.loan_id:
            skipped.append({"id": tx_id, "reason": LOCKED})
            continue

        if data.action == "delete":
            purge_files_for(db, user.id, [tx_id])
            apply_to_card(db, tx.account_id, tx.kind, tx.amount, -1)
            db.delete(tx)
        elif data.action == "set_category":
            if category and category.kind != tx.kind:
                skipped.append({"id": tx_id, "reason": "la categoría es de otro tipo (ingreso/gasto)"})
                continue
            tx.category_id = category.id if category else None
            if category:
                learn(db, user.id, tx.note, category.id)
        else:
            names = tx.tag_names
            if data.action == "add_tag":
                if tag in names:
                    skipped.append({"id": tx_id, "reason": "ya tenía esa etiqueta"})
                    continue
                if len(names) >= MAX_TAGS_PER_TX:
                    skipped.append({"id": tx_id, "reason": f"ya tiene {MAX_TAGS_PER_TX} etiquetas"})
                    continue
                set_tags(db, user.id, tx, [*names, tag])
            else:
                if tag not in names:
                    skipped.append({"id": tx_id, "reason": "no tenía esa etiqueta"})
                    continue
                set_tags(db, user.id, tx, [n for n in names if n != tag])
            db.flush()  # sin esto, una etiqueta nueva no se vería en el siguiente movimiento y se crearía repetida
        affected += 1
    db.commit()
    return {"action": data.action, "affected": affected, "skipped": skipped, "not_found": not_found}
