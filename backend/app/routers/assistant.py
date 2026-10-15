from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..services.assistant import insights

router = APIRouter(prefix="/assistant", tags=["asistente"])


@router.get("")
def assistant(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Observaciones y consejos calculados con tus datos de hoy."""
    return {"generated": date.today().isoformat(), "insights": insights(db, user.id)}
