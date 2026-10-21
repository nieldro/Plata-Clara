"""Resumen de la semana en curso (lunes a domingo) comparado con la misma parte de la semana anterior."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Category, Transaction


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # lunes


def weekly_summary(db: Session, user_id: int, today: date | None = None) -> dict:
    today = today or clock.today()
    start = week_start(today)
    prev_start = start - timedelta(days=7)
    elapsed = (today - start).days + 1  # lunes = 1

    rows = db.execute(
        select(Transaction.date, Transaction.kind, Transaction.amount, Transaction.category_id, Transaction.note)
        .where(Transaction.user_id == user_id, Transaction.transfer_id.is_(None), Transaction.loan_id.is_(None),
               Transaction.date >= prev_start, Transaction.date <= today)
        .order_by(Transaction.date, Transaction.id)).all()

    income = expense = prev_expense = prev_income = Decimal(0)
    per_day: dict[date, Decimal] = defaultdict(Decimal)
    per_cat: dict[int | None, Decimal] = defaultdict(Decimal)
    biggest, count = None, 0
    for when, kind, amount, cat_id, note in rows:
        if when >= start:
            count += 1
            if kind == "income":
                income += amount
            else:
                expense += amount
                per_day[when] += amount
                per_cat[cat_id] += amount
                if biggest is None or amount > biggest["amount"]:
                    biggest = {"date": when, "amount": amount, "note": note or "", "category_id": cat_id}
        elif (when - prev_start).days < elapsed:  # solo la misma porción de la semana pasada (lunes a hoy-7)
            if kind == "income":
                prev_income += amount
            else:
                prev_expense += amount

    names = dict(db.execute(select(Category.id, Category.name).where(Category.user_id == user_id)).all())
    top = sorted(per_cat.items(), key=lambda kv: -kv[1])[:3]
    if biggest:
        biggest["category"] = names.get(biggest.pop("category_id"), "Sin categoría")
    change = round(float((expense - prev_expense) / prev_expense * 100), 1) if prev_expense > 0 else None
    return {
        "week_start": start, "week_end": start + timedelta(days=6), "today": today, "days_elapsed": elapsed,
        "income": income, "expense": expense, "net": income - expense, "transactions": count,
        "previous_expense": prev_expense, "previous_income": prev_income, "expense_change_pct": change,
        "daily_average": (expense / elapsed).quantize(Decimal("0.01")),
        "daily": [{"date": (d := start + timedelta(days=i)), "expense": per_day.get(d, Decimal(0)), "future": d > today}
                  for i in range(7)],
        "top_categories": [{"category": names.get(c, "Sin categoría"), "total": t} for c, t in top],
        "biggest_expense": biggest,
    }
