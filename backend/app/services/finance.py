"""Matemática financiera pura (sin base de datos), fácil de probar.

Los cálculos usan float y se redondean a 2 decimales; es una simulación,
no contabilidad. Los saldos reales se guardan en Decimal en la base.
"""

MAX_MONTHS = 600


def monthly_rate(rate_pct: float, rate_type: str = "EA") -> float:
    """Convierte una tasa en % a tasa mensual efectiva (fracción).

    EA: efectiva anual (la que publican los bancos en Colombia)
    MV: mensual vencida (ya es mensual)
    NA: nominal anual capitalizada mensualmente (se divide en 12)
    """
    r = rate_pct / 100
    if rate_type == "EA":
        return (1 + r) ** (1 / 12) - 1
    if rate_type == "MV":
        return r
    if rate_type == "NA":
        return r / 12
    raise ValueError(f"Tipo de tasa desconocido: {rate_type}")


def loan_payment(principal: float, r: float, n: int) -> float:
    """Cuota fija mensual (sistema francés)."""
    if n <= 0:
        raise ValueError("El plazo debe ser mayor a 0")
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def amortize(balance: float, r: float, payment: float, extra: float = 0.0) -> dict:
    """Simula pagos mensuales hasta saldar la deuda.

    Sirve para créditos (cuota fija) y tarjetas (pago que tú eliges).
    Lanza ValueError si el pago no alcanza ni para cubrir los intereses.
    """
    pay = payment + extra
    if balance <= 0:
        return {"months": 0, "total_interest": 0.0, "total_paid": 0.0, "rows": []}
    if pay <= balance * r:
        raise ValueError(
            "El pago mensual no cubre ni los intereses: la deuda nunca se salda. "
            f"Mínimo necesario: {balance * r + 0.01:.2f}"
        )
    rows, total_interest, month = [], 0.0, 0
    while balance > 0.005 and month < MAX_MONTHS:
        month += 1
        interest = balance * r
        paid = min(pay, balance + interest)
        principal = paid - interest
        balance -= principal
        total_interest += interest
        rows.append({
            "n": month,
            "payment": round(paid, 2),
            "interest": round(interest, 2),
            "principal": round(principal, 2),
            "balance": round(max(balance, 0), 2),
        })
    return {
        "months": month,
        "total_interest": round(total_interest, 2),
        "total_paid": round(sum(x["payment"] for x in rows), 2),
        "rows": rows,
    }


def savings_required(target: float, current: float, r: float, n: int) -> float:
    """Aporte mensual (al final de cada mes) para llegar a `target` en n meses."""
    if n <= 0:
        raise ValueError("El plazo debe ser mayor a 0")
    grown = current * (1 + r) ** n
    missing = target - grown
    if missing <= 0:
        return 0.0
    if r == 0:
        return missing / n
    return missing * r / ((1 + r) ** n - 1)


def months_between(start, end) -> int:
    return max((end.year - start.year) * 12 + end.month - start.month, 1)
