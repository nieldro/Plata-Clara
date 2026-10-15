from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import Budget, Category, User
from ..schemas import BudgetIn
from ..services.queries import budget_rows, current_month

router = APIRouter(prefix="/budgets", tags=["presupuestos"])


@router.get("")
def list_budgets(month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                 db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Presupuestos con el gasto real del mes (por defecto, el mes actual)."""
    month = month or current_month()
    return {"month": month, "items": budget_rows(db, user.id, month)}


@router.put("/{category_id}")
def set_budget(category_id: int, data: BudgetIn,
               db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Crea o cambia el tope mensual de una categoría de gasto."""
    cat = owned(db, Category, category_id, user)
    if cat.kind != "expense":
        raise HTTPException(422, "Solo las categorías de gasto pueden tener presupuesto")
    budget = db.scalar(select(Budget).where(Budget.user_id == user.id, Budget.category_id == cat.id))
    if budget:
        budget.amount = data.amount
    else:
        db.add(Budget(user_id=user.id, category_id=cat.id, amount=data.amount))
    db.commit()
    return {"category_id": cat.id, "amount": data.amount}


@router.delete("/{category_id}", status_code=204)
def delete_budget(category_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    budget = db.scalar(select(Budget).where(Budget.user_id == user.id, Budget.category_id == category_id))
    if not budget:
        raise HTTPException(404, "No encontrado")
    db.delete(budget)
    db.commit()
