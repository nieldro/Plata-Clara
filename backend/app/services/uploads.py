"""Subida segura de archivos: tamaño limitado, tipo verificado por sus bytes y rutas generadas por nosotros."""
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Attachment

# tipo → (extensión, firma). Se mira el contenido real: el Content-Type que envía el cliente no es confiable.
SIGNATURES = {
    "image/jpeg": (".jpg", lambda b: b.startswith(b"\xff\xd8\xff")),
    "image/png": (".png", lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/webp": (".webp", lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP"),
    "application/pdf": (".pdf", lambda b: b.startswith(b"%PDF-")),
}


async def read_limited(file: UploadFile) -> bytes:
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"El archivo supera los {settings.max_upload_mb} MB")
    return data


def detect_type(data: bytes) -> str | None:
    for content_type, (_, matches) in SIGNATURES.items():
        if matches(data):
            return content_type
    return None


def safe_display_name(name: str | None) -> str:
    """Solo para mostrar: sin carpetas, sin caracteres de control, máx. 100."""
    base = (name or "recibo").replace("\\", "/").split("/")[-1]
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    return (base or "recibo")[:100]


def user_dir(user_id: int) -> Path:
    path = Path(settings.upload_dir).resolve() / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(user_id: int, data: bytes, content_type: str) -> str:
    stored = f"{uuid.uuid4().hex}{SIGNATURES[content_type][0]}"
    (user_dir(user_id) / stored).write_bytes(data)
    return stored


def path_of(user_id: int, stored_name: str) -> Path:
    """Ruta del archivo, garantizando que queda dentro de la carpeta del usuario."""
    base = user_dir(user_id)
    path = (base / stored_name).resolve()
    if base not in path.parents:
        raise HTTPException(404, "No encontrado")
    return path


def remove(user_id: int, stored_name: str) -> None:
    try:
        path_of(user_id, stored_name).unlink(missing_ok=True)
    except (OSError, HTTPException):
        pass  # un archivo que ya no está no debe impedir borrar el movimiento


def purge_files_for(db: Session, user_id: int, tx_ids: list[int]) -> None:
    """Borra del disco los archivos de estos movimientos (las filas caen con el movimiento)."""
    if not tx_ids:
        return
    for stored in db.scalars(select(Attachment.stored_name).where(
            Attachment.user_id == user_id, Attachment.transaction_id.in_(tx_ids))):
        remove(user_id, stored)
