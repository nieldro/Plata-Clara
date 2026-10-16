from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": int(now.timestamp()),
               "exp": now + timedelta(minutes=settings.token_minutes)}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token_full(token: str) -> tuple[int, int] | None:
    """(id de usuario, momento de emisión en segundos) o None si el token no vale."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return int(payload["sub"]), int(payload.get("iat", 0))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def decode_token(token: str) -> int | None:
    decoded = decode_token_full(token)
    return decoded[0] if decoded else None


def utcnow_naive() -> datetime:
    """Ahora en UTC sin zona horaria (como se guardan las fechas en la base)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
