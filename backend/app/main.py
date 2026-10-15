from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from . import models  # noqa: F401  (registra las tablas)
from .db import Base, engine
from .routers import auth, budgets, core, debts, savings, simulator


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Para producción reemplazar por migraciones con Alembic.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Finanzas Personales", version="0.1.0", lifespan=lifespan)

api = APIRouter(prefix="/api")
for r in (auth.router, core.router, budgets.router, debts.router, savings.router, simulator.router):
    api.include_router(r)
app.include_router(api)


@app.get("/health")
def health():
    return {"status": "ok"}
