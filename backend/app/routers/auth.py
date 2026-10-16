from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Category, User
from ..schemas import RegisterIn, TokenOut, UserOut
from ..security import create_token, hash_password, verify_password
from ..services import ratelimit


def _too_many(seconds: int, what: str) -> HTTPException:
    minutes = max(1, round(seconds / 60))
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                         f"Demasiados {what}. Intenta de nuevo en {minutes} minuto{'s' if minutes != 1 else ''}.",
                         headers={"Retry-After": str(seconds)})


def _client_ip(request: Request) -> str:
    # Se usa la IP de la conexión. Detrás de un proxy de confianza (nginx) hay que configurar uvicorn con
    # --proxy-headers y --forwarded-allow-ips para que aquí llegue la IP real y no la del proxy.
    return request.client.host if request.client else "desconocida"


router = APIRouter(prefix="/auth", tags=["auth"])

DEFAULT_CATEGORIES = [
    ("Salario", "income"), ("Otros ingresos", "income"),
    ("Mercado", "expense"), ("Transporte", "expense"), ("Arriendo", "expense"),
    ("Servicios", "expense"), ("Salud", "expense"), ("Ocio", "expense"),
    ("Pago de deudas", "expense"),
]


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    wait = ratelimit.register_limiter.retry_after(ip)
    if wait:
        raise _too_many(wait, "registros desde esta conexión")
    ratelimit.register_limiter.record(ip)
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese correo ya está registrado")
    user = User(email=email, name=data.name, password_hash=hash_password(data.password))
    db.add(user)
    db.flush()
    db.add_all(Category(user_id=user.id, name=n, kind=k) for n, k in DEFAULT_CATEGORIES)
    db.commit()
    return user


@router.post("/login", response_model=TokenOut)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    ip = _client_ip(request)
    pair_key = f"{ip}|{form.username.strip().lower()}"
    # Se mira el bloqueo ANTES de revisar la contraseña: así una cuenta bloqueada no sirve para seguir adivinando,
    # y un correo que no existe se bloquea igual que uno que sí (no se puede averiguar quién tiene cuenta).
    wait = max(ratelimit.login_limiter.retry_after(pair_key), ratelimit.login_ip_limiter.retry_after(ip))
    if wait:
        raise _too_many(wait, "intentos fallidos")

    user = db.scalar(select(User).where(User.email == form.username.strip().lower()))
    if not user or not verify_password(form.password, user.password_hash):
        ratelimit.login_limiter.record(pair_key)
        ratelimit.login_ip_limiter.record(ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    ratelimit.login_limiter.reset(pair_key)
    return TokenOut(access_token=create_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
