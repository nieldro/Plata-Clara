from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..services.queries import current_month
from ..services.report import build_report

router = APIRouter(prefix="/reports", tags=["informes"])


@router.get("/monthly")
def monthly_report(month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                   db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Informe del mes (YYYY-MM, por defecto el actual) en PDF."""
    month = month or current_month()
    return Response(build_report(db, user, month), media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="plata-clara-informe-{month}.pdf"',
        "Cache-Control": "no-store",
    })
