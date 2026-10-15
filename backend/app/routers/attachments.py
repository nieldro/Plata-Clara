from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import Attachment, Transaction, User
from ..services import uploads

router = APIRouter(tags=["recibos"])

MAX_PER_TX = 5


def _out(a: Attachment) -> dict:
    return {"id": a.id, "filename": a.filename, "content_type": a.content_type, "size": a.size,
            "created_at": a.created_at}


@router.get("/transactions/{tx_id}/attachments")
def list_attachments(tx_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    tx = owned(db, Transaction, tx_id, user)
    return [_out(a) for a in tx.attachments]


@router.post("/transactions/{tx_id}/attachments", status_code=201)
async def add_attachment(tx_id: int, file: UploadFile = File(...),
                         db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Adjunta la foto (JPG, PNG, WEBP) o el PDF de un recibo a un movimiento."""
    tx = owned(db, Transaction, tx_id, user)
    if len(tx.attachments) >= MAX_PER_TX:
        raise HTTPException(422, f"Máximo {MAX_PER_TX} archivos por movimiento")
    data = await uploads.read_limited(file)
    if not data:
        raise HTTPException(422, "El archivo está vacío")
    content_type = uploads.detect_type(data)
    if not content_type:
        raise HTTPException(415, "Solo se aceptan imágenes JPG, PNG, WEBP o PDF")
    stored = uploads.save(user.id, data, content_type)
    att = Attachment(user_id=user.id, transaction_id=tx.id, filename=uploads.safe_display_name(file.filename),
                     stored_name=stored, content_type=content_type, size=len(data))
    db.add(att)
    db.commit()
    db.refresh(att)
    return _out(att)


@router.get("/attachments/{attachment_id}/file")
def download(attachment_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    att = owned(db, Attachment, attachment_id, user)
    path = uploads.path_of(user.id, att.stored_name)
    if not path.is_file():
        raise HTTPException(404, "El archivo ya no está disponible")
    return FileResponse(path, media_type=att.content_type, filename=att.filename, content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"})


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(attachment_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    att = owned(db, Attachment, attachment_id, user)
    uploads.remove(user.id, att.stored_name)
    db.delete(att)
    db.commit()
