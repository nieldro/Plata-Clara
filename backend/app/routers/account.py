
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .. import clock
from ..db import get_db
from ..deps import current_user
from ..models import User
from ..schemas import ChangePasswordIn, DeleteAccountIn, TokenOut
from ..security import create_token, hash_password, utcnow_naive, verify_password
from ..services import account as svc
from ..services import ratelimit

router = APIRouter(prefix="/account", tags=["cuenta"])


def _check_password(user: User, password: str) -> None:
    """Pide la contraseña actual; los fallos cuentan para el límite de intentos (como en el login)."""
    key = f"acct|{user.id}"
    wait = ratelimit.login_limiter.retry_after(key)
    if wait:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Demasiados intentos. Intenta de nuevo en {max(1, round(wait / 60))} minuto(s).",
                            headers={"Retry-After": str(wait)})
    if not verify_password(password, user.password_hash):
        ratelimit.login_limiter.record(key)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La contraseña actual no es correcta")
    ratelimit.login_limiter.reset(key)


@router.post("/password", response_model=TokenOut)
def change_password(data: ChangePasswordIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Cambia la contraseña y cierra todas las demás sesiones; devuelve una sesión nueva para esta."""
    _check_password(user, data.current_password)
    if data.new_password == data.current_password:
        raise HTTPException(422, "La contraseña nueva debe ser distinta de la actual")
    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = utcnow_naive()
    db.commit()
    return TokenOut(access_token=create_token(user.id))


@router.post("/logout-all", response_model=TokenOut)
def logout_everywhere(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Cierra todas las sesiones abiertas (otros dispositivos, un celular perdido…) y deja esta con una sesión nueva."""
    user.password_changed_at = utcnow_naive()  # el mismo mecanismo que al cambiar la contraseña: invalida lo anterior
    db.commit()
    return TokenOut(access_token=create_token(user.id))


@router.get("/export")
def export(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Descarga todos tus datos en un archivo JSON."""
    body = svc.export_data(db, user)
    return Response(body, media_type="application/json", headers={
        "Content-Disposition": f'attachment; filename="plata-clara-datos-{clock.today().isoformat()}.json"',
        "Cache-Control": "no-store",
    })


@router.post("/delete", status_code=204)
def delete_account(data: DeleteAccountIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Borra tu cuenta y TODOS tus datos (movimientos, recibos, metas, préstamos…). No se puede deshacer."""
    _check_password(user, data.password)
    svc.delete_user(db, user)
