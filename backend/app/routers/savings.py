from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import SavingsGoal, User
from ..schemas import ContributionIn, GoalIn, GoalOut
from ..services import finance

router = APIRouter(prefix="/savings", tags=["ahorro"])


@router.get("", response_model=list[GoalOut])
def list_goals(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(SavingsGoal).where(SavingsGoal.user_id == user.id).order_by(SavingsGoal.id)).all()


@router.post("", response_model=GoalOut, status_code=201)
def create_goal(data: GoalIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal = SavingsGoal(user_id=user.id, **data.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(owned(db, SavingsGoal, goal_id, user))
    db.commit()


@router.post("/{goal_id}/contributions", response_model=GoalOut)
def contribute(goal_id: int, data: ContributionIn,
               db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal = owned(db, SavingsGoal, goal_id, user)
    goal.current_amount += data.amount
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/{goal_id}/plan")
def plan(goal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Cuánto ahorrar cada mes para llegar a la meta en la fecha objetivo."""
    goal = owned(db, SavingsGoal, goal_id, user)
    n = finance.months_between(date.today(), goal.target_date)
    r = finance.monthly_rate(float(goal.annual_rate), "EA")
    monthly = finance.savings_required(float(goal.target_amount), float(goal.current_amount), r, n)
    return {
        "months_left": n,
        "monthly_contribution": round(monthly, 2),
        "missing": round(float(goal.target_amount - goal.current_amount), 2),
        "progress_pct": round(float(goal.current_amount / goal.target_amount) * 100, 1),
    }
