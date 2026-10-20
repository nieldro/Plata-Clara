"""Resumen de un año: cada mes, totales, mejor y peor mes y gasto por categoría."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category
from .queries import month_totals, spent_by_category

TOP_CATEGORIES = 8


def annual_summary(db: Session, user_id: int, year: int) -> dict:
    months = []
    for m in range(1, 13):
        income, expense = month_totals(db, user_id, f"{year}-{m:02d}")
        months.append({"month": f"{year}-{m:02d}", "income": income, "expense": expense, "net": income - expense})

    income = sum((m["income"] for m in months), Decimal(0))
    expense = sum((m["expense"] for m in months), Decimal(0))
    active = [m for m in months if m["income"] or m["expense"]]

    by_cat = spent_by_category(db, user_id, date(year, 1, 1), date(year + 1, 1, 1))
    names = dict(db.execute(select(Category.id, Category.name).where(Category.user_id == user_id)).all())
    ranked = sorted(by_cat.items(), key=lambda kv: -kv[1])
    categories = [{"category": names.get(c, "Sin categoría"), "total": t,
                   "pct": round(float(t / expense * 100), 1) if expense else 0.0} for c, t in ranked[:TOP_CATEGORIES]]

    return {
        "year": year, "income": income, "expense": expense, "net": income - expense,
        "savings_rate": round(float((income - expense) / income * 100), 1) if income > 0 else None,
        "active_months": len(active),
        "avg_monthly_expense": (expense / len(active)).quantize(Decimal("0.01")) if active else Decimal(0),
        "best_month": max(active, key=lambda m: m["net"])["month"] if active else None,
        "worst_month": min(active, key=lambda m: m["net"])["month"] if active else None,
        "months": months, "top_categories": categories,
    }
