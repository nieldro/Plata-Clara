from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import SavingsContribution, SavingsGoal, User
from ..schemas import ContributionIn, ContributionOut, GoalIn, GoalOut, GoalUpdate
from ..services import finance

router = APIRouter(prefix="/savings", tags=["ahorro"])


@router.get("", response_model=list[GoalOut])
def list_goals(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(SavingsGoal).where(SavingsGoal.user_id == user.id).order_by(SavingsGoal.id)).all()


@router.post("", response_model=GoalOut, status_code=201)
def create_goal(data: GoalIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal = SavingsGoal(user_id=user.id, **data.model_dump())
    db.add(goal)
    db.flush()
    if data.current_amount > 0:  # lo que ya tenías queda como primer aporte
        db.add(SavingsContribution(goal_id=goal.id, amount=data.current_amount, date=date.today(), note="Saldo inicial"))
    db.commit()
    db.refresh(goal)
    return goal


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, data: GoalUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal = owned(db, SavingsGoal, goal_id, user)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal = owned(db, SavingsGoal, goal_id, user)
    db.query(SavingsContribution).filter(SavingsContribution.goal_id == goal.id).delete()
    db.delete(goal)
    db.commit()


@router.post("/{goal_id}/contributions", response_model=GoalOut)
def contribute(goal_id: int, data: ContributionIn,
               db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal = owned(db, SavingsGoal, goal_id, user)
    signed = data.amount if data.kind == "deposit" else -data.amount
    if goal.current_amount + signed < 0:
        raise HTTPException(422, "No puedes retirar más de lo que has ahorrado en esta meta")
    goal.current_amount += signed
    db.add(SavingsContribution(goal_id=goal.id, amount=signed, date=data.date or date.today(), note=data.note))
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/{goal_id}/contributions", response_model=list[ContributionOut])
def list_contributions(goal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned(db, SavingsGoal, goal_id, user)
    return db.scalars(
        select(SavingsContribution).where(SavingsContribution.goal_id == goal_id)
        .order_by(SavingsContribution.date.desc(), SavingsContribution.id.desc())
    ).all()


@router.delete("/{goal_id}/contributions/{contribution_id}", response_model=GoalOut)
def delete_contribution(goal_id: int, contribution_id: int,
                        db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Borra un aporte o retiro y revierte su efecto en la meta."""
    goal = owned(db, SavingsGoal, goal_id, user)
    c = db.get(SavingsContribution, contribution_id)
    if not c or c.goal_id != goal.id:
        raise HTTPException(404, "No encontrado")
    goal.current_amount = max(goal.current_amount - c.amount, 0)
    db.delete(c)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/{goal_id}/plan")
def plan(goal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Cuánto ahorrar cada mes para llegar a la meta, y cómo crecería mes a mes."""
    goal = owned(db, SavingsGoal, goal_id, user)
    today = date.today()
    n = finance.months_between(today, goal.target_date)
    r = finance.monthly_rate(float(goal.annual_rate), "EA")
    target, current = float(goal.target_amount), float(goal.current_amount)
    monthly = finance.savings_required(target, current, r, n)

    balance, projection = current, []
    for i in range(n + 1):
        year, month0 = divmod(today.year * 12 + today.month - 1 + i, 12)
        projection.append({"month": i, "label": f"{year}-{month0 + 1:02d}", "balance": round(balance, 2)})
        balance = balance * (1 + r) + monthly

    return {
        "months_left": n,
        "monthly_contribution": round(monthly, 2),
        "missing": round(target - current, 2),
        "progress_pct": round(current / target * 100, 1),
        "projection": projection,
    }
