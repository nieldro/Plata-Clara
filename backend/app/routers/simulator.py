"""Simuladores sin guardar nada: 'qué pasaría si...'."""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import current_user
from ..schemas import LoanSimIn, PayoffSimIn, SavingsSimIn
from ..services import finance

router = APIRouter(prefix="/simulator", tags=["simulador"], dependencies=[Depends(current_user)])


@router.post("/loan")
def loan(data: LoanSimIn):
    """Cuota y costo total de un crédito; con `extra` muestra el ahorro en intereses."""
    r = finance.monthly_rate(data.rate, data.rate_type)
    payment = finance.loan_payment(data.amount, r, data.months)
    base = finance.amortize(data.amount, r, payment)
    plan = finance.amortize(data.amount, r, payment, data.extra)
    return {
        "monthly_rate_pct": round(r * 100, 4),
        "payment": round(payment, 2),
        "months": plan["months"],
        "total_interest": plan["total_interest"],
        "total_paid": plan["total_paid"],
        "months_saved": base["months"] - plan["months"],
        "interest_saved": round(base["total_interest"] - plan["total_interest"], 2),
        "rows": plan["rows"],
    }


@router.post("/payoff")
def payoff(data: PayoffSimIn):
    """Tarjeta de crédito: ¿en cuántos meses la pago con X al mes y cuánto interés pago?"""
    r = finance.monthly_rate(data.rate, data.rate_type)
    try:
        plan = finance.amortize(data.balance, r, data.payment)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"monthly_rate_pct": round(r * 100, 4), **plan}


@router.post("/savings")
def savings(data: SavingsSimIn):
    """Aporte mensual necesario para llegar a una meta."""
    r = finance.monthly_rate(data.rate, data.rate_type)
    monthly = finance.savings_required(data.target, data.current, r, data.months)
    return {
        "monthly_contribution": round(monthly, 2),
        "total_contributed": round(monthly * data.months, 2),
        "interest_earned": round(data.target - data.current - monthly * data.months, 2),
    }
