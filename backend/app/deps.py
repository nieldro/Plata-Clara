from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import decode_token

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    user_id = decode_token(token)
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida")
    return user


def owned(db: Session, model, obj_id: int, user: User):
    """Trae un registro solo si pertenece al usuario; si no, 404."""
    obj = db.get(model, obj_id)
    if not obj or getattr(obj, "user_id", user.id) != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrado")
    return obj
