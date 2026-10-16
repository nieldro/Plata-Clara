from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from . import models  # noqa: F401  (registra las tablas)
from .migrate import run_migrations
from .routers import (assistant, attachments, auth, budgets, core, debts, imports, loans, notifications,
                      recurring, rules, savings, simulator, tags)


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()  # lleva la base al esquema actual (crea las tablas la primera vez)
    yield


app = FastAPI(title="Finanzas Personales", version="0.1.0", lifespan=lifespan)

api = APIRouter(prefix="/api")
for r in (auth.router, core.router, budgets.router, recurring.router, notifications.router,
          assistant.router, tags.router, rules.router, imports.router, attachments.router, loans.router, debts.router, savings.router, simulator.router):
    api.include_router(r)
app.include_router(api)


@app.get("/health")
def health():
    return {"status": "ok"}
