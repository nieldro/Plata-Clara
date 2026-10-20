from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..services.upcoming import upcoming

router = APIRouter(prefix="/upcoming", tags=["próximos pagos"])


@router.get("")
def list_upcoming(days: int = Query(30, ge=1, le=180), db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    """Pagos e ingresos esperados en los próximos días: recurrentes, vencimientos de tarjetas/créditos y préstamos."""
    items = upcoming(db, user.id, days)
    pay = sum((i["amount"] or 0 for i in items if i["kind"] == "expense"), 0)
    receive = sum((i["amount"] or 0 for i in items if i["kind"] == "income"), 0)
    return {"days": days, "to_pay": pay, "to_receive": receive, "items": items}
