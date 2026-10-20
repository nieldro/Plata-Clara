from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..services.merchants import top_merchants
from ..services.queries import current_month

router = APIRouter(prefix="/insights", tags=["análisis"])


@router.get("/merchants")
def merchants(month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), limit: int = Query(10, ge=1, le=30),
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Dónde más gastas: gasto del mes agrupado por comercio (según la nota de cada movimiento)."""
    return top_merchants(db, user.id, month or current_month(), limit)
