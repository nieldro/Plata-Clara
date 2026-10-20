from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..services.networth import net_worth

router = APIRouter(prefix="/net-worth", tags=["patrimonio"])


@router.get("")
def history(months: int = Query(12, ge=2, le=36), db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Patrimonio neto al cierre de cada mes (dinero en cuentas menos deudas) y cuánto cambió en el período."""
    points = net_worth(db, user.id, months)
    change = points[-1]["net_worth"] - points[0]["net_worth"] if len(points) > 1 else 0
    return {"months": len(points), "change": change, "points": points}
