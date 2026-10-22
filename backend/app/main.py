from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models  # noqa: F401  (registra las tablas)
from .config import settings
from .db import get_db
from .migrate import run_migrations
from .routers import (account, assistant, attachments, auth, budgets, bulk, core, debts, exports, imports, insights,
                      loans, networth, notifications, quickadd, recurring, reports, rules, saved_filters,
                      savings, simulator, tags, upcoming)


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()  # lleva la base al esquema actual (crea las tablas la primera vez)
    yield


DESCRIPTION = """
API de **Plata Clara**: cuentas, movimientos, presupuestos, deudas, ahorro, préstamos entre personas,
importación de extractos, informes y un asistente que sugiere qué hacer con tu dinero.

Todas las rutas (salvo registro, inicio de sesión y `/health`) piden el encabezado
`Authorization: Bearer <token>` que entrega `POST /api/auth/login`.
"""


def docs_urls(environment: str) -> dict[str, str | None]:
    """La documentación interactiva sirve en desarrollo; en producción no se publica el mapa de la API."""
    if environment == "production":
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


app = FastAPI(
    title="Plata Clara",
    version="0.1.0",
    description=DESCRIPTION,
    lifespan=lifespan,
    **docs_urls(settings.environment),
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",     # el navegador no «adivina» el tipo de un archivo
    "X-Frame-Options": "DENY",               # nadie puede incrustar la API en un iframe
    "Referrer-Policy": "no-referrer",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if request.url.path.startswith("/api"):
        # Datos financieros privados: que ni el navegador ni un proxy los guarden. Un endpoint que
        # necesite otra política (como la descarga de recibos) ya la trae puesta y se respeta.
        response.headers.setdefault("Cache-Control", "no-store")
    return response

api = APIRouter(prefix="/api")
for r in (
    auth.router, account.router, bulk.router, core.router, exports.router, reports.router, budgets.router, recurring.router,
    notifications.router, assistant.router, tags.router, rules.router, imports.router, attachments.router,
    loans.router, debts.router, savings.router, simulator.router, upcoming.router, networth.router,
    insights.router, quickadd.router, saved_filters.router,
):
    api.include_router(r)
app.include_router(api)


@app.get("/health")
def health():
    """¿El proceso está vivo? (no mira la base de datos)"""
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    """¿Puede atender peticiones? Comprueba que la base de datos responde; si no, 503."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, {"status": "error", "database": "down"}) from e
    return {"status": "ok", "database": "ok"}
