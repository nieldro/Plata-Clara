from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import Budget, Category, User
from ..schemas import ApplyBudgetsIn, BudgetIn
from ..services.budget_suggestions import suggestions
from ..services.queries import budget_rows, current_month

router = APIRouter(prefix="/budgets", tags=["presupuestos"])


@router.get("")
def list_budgets(month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                 db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Presupuestos con el gasto real del mes (por defecto, el mes actual)."""
    month = month or current_month()
    return {"month": month, "items": budget_rows(db, user.id, month)}


@router.get("/suggestions")
def budget_suggestions(months: int = Query(3, ge=1, le=12), db: Session = Depends(get_db),
                       user: User = Depends(current_user)):
    """Topes sugeridos según el promedio de lo que gastaste en los últimos meses completos."""
    return suggestions(db, user.id, months)


@router.post("/suggestions/apply")
def apply_suggestions(data: ApplyBudgetsIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Crea (o actualiza) varios presupuestos de una vez con los montos que elegiste."""
    cats = {c.id: c for c in db.scalars(select(Category).where(
        Category.user_id == user.id, Category.id.in_([i.category_id for i in data.items])))}
    existing = {b.category_id: b for b in db.scalars(select(Budget).where(Budget.user_id == user.id))}
    created = updated = 0
    for item in data.items:
        cat = cats.get(item.category_id)
        if cat is None:
            raise HTTPException(404, "Una de las categorías no existe")
        if cat.kind != "expense":
            raise HTTPException(422, f"«{cat.name}» no es una categoría de gasto")
        if item.category_id in existing:
            existing[item.category_id].amount = item.amount
            updated += 1
        else:
            db.add(Budget(user_id=user.id, category_id=item.category_id, amount=item.amount))
            created += 1
    db.commit()
    return {"created": created, "updated": updated}


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
