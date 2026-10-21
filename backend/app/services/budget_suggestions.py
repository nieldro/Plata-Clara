"""Presupuestos sugeridos a partir de lo que realmente gastas por categoría en los últimos meses."""
import math
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Budget, Category
from .queries import month_bounds, prev_month, spent_by_category

STEP = 10_000        # los topes se redondean hacia arriba a múltiplos de $10.000
MARGIN = Decimal("1.05")  # 5 % de holgura sobre el promedio


def round_up(amount: Decimal, step: int = STEP) -> int:
    return max(step, math.ceil(amount / step) * step)


def suggestions(db: Session, user_id: int, months: int = 3, today: date | None = None) -> dict:
    """Promedio mensual por categoría de gasto en los últimos `months` meses COMPLETOS (el mes en curso no cuenta,
    porque está a medias) y un tope sugerido. Se marca cuáles ya tienen presupuesto."""
    today = today or clock.today()
    first = today.strftime("%Y-%m")
    for _ in range(months):
        first = prev_month(first)
    start = month_bounds(first)[0]
    end = month_bounds(today.strftime("%Y-%m"))[0]

    spent = spent_by_category(db, user_id, start, end)
    cats = {c.id: c for c in db.scalars(select(Category).where(Category.user_id == user_id, Category.kind == "expense"))}
    budgeted = {b.category_id: b.amount for b in db.scalars(select(Budget).where(Budget.user_id == user_id))}

    items = []
    for cat_id, total in spent.items():
        cat = cats.get(cat_id)
        if cat is None or total <= 0:  # «sin categoría» no se puede presupuestar
            continue
        average = (total / months).quantize(Decimal("0.01"))
        items.append({
            "category_id": cat_id, "category": cat.name, "average": average,
            "suggested": round_up(average * MARGIN), "has_budget": cat_id in budgeted,
            "current_budget": budgeted.get(cat_id),
        })
    items.sort(key=lambda i: -i["average"])
    return {"months": months, "from": start, "to": end, "items": items}
