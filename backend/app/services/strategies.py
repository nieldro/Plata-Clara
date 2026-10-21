"""Estrategias para salir de varias deudas: avalancha (la más cara primero) y bola de nieve (la más pequeña primero)."""
from dataclasses import dataclass, field

from . import finance

MAX_MONTHS = finance.MAX_MONTHS


@dataclass
class DebtState:
    id: int
    name: str
    balance: float
    rate: float        # tasa mensual efectiva (fracción)
    minimum: float     # pago mínimo mensual
    paid_in: int | None = None  # mes en que se salda
    interest_paid: float = 0.0
    history: list = field(default_factory=list)


def minimum_payment(balance: float, r: float, monthly_payment: float | None, term_months: int | None) -> float:
    """Pago mínimo de una deuda: el que declaró el usuario, la cuota del plazo o, si no hay datos,
    el interés del mes más 1 % del saldo (lo habitual en tarjetas)."""
    if monthly_payment:
        return float(monthly_payment)
    if term_months:
        return finance.loan_payment(balance, r, term_months)
    return balance * r + balance * 0.01


def states_from_debts(debts) -> list[DebtState]:
    """Convierte las deudas guardadas (modelo Debt) en el estado que usa la simulación."""
    out = []
    for d in debts:
        r = finance.monthly_rate(float(d.rate), d.rate_type)
        balance = float(d.current_balance)
        out.append(DebtState(d.id, d.name, balance, r, minimum_payment(balance, r, d.monthly_payment, d.term_months)))
    return out


def simulate(debts: list[DebtState], budget: float, order, rollover: bool = True) -> dict:
    """Simula mes a mes. `order` decide a cuál deuda va lo que sobra después de pagar los mínimos."""
    states = [DebtState(d.id, d.name, d.balance, d.rate, d.minimum) for d in debts]
    month = 0
    while any(d.balance > 0.005 for d in states) and month < MAX_MONTHS:
        month += 1
        for d in states:
            if d.balance > 0.005:
                interest = d.balance * d.rate
                d.balance += interest
                d.interest_paid += interest
        left = budget
        for d in states:  # primero los mínimos
            if d.balance > 0.005:
                pay = min(d.minimum, d.balance, left)
                d.balance -= pay
                left -= pay
        if rollover:  # lo que sobra (y los mínimos de deudas ya saldadas) ataca la prioritaria
            for d in sorted((s for s in states if s.balance > 0.005), key=order):
                pay = min(left, d.balance)
                d.balance -= pay
                left -= pay
                if left <= 0.005:
                    break
        for d in states:
            if d.balance <= 0.005 and d.paid_in is None:
                d.paid_in = month
                d.balance = 0.0
    done = all(d.balance <= 0.005 for d in states)
    return {
        "finished": done,
        "months": month if done else None,
        "total_interest": round(sum(d.interest_paid for d in states), 2),
        "order": [{"id": d.id, "name": d.name, "paid_in_month": d.paid_in}
                  for d in sorted(states, key=lambda s: (s.paid_in is None, s.paid_in or 0))],
    }


def compare(debts: list[DebtState], extra: float) -> dict:
    """Avalancha, bola de nieve y «solo mínimos» (sin reasignar lo liberado) con el mismo presupuesto mensual."""
    base = sum(d.minimum for d in debts)
    budget = base + extra
    avalanche = simulate(debts, budget, order=lambda d: (-d.rate, d.balance))
    snowball = simulate(debts, budget, order=lambda d: (d.balance, -d.rate))
    minimums = simulate(debts, base, order=lambda d: d.balance, rollover=False)
    return {"monthly_budget": round(budget, 2), "minimums_total": round(base, 2),
            "avalanche": avalanche, "snowball": snowball, "minimums_only": minimums}
