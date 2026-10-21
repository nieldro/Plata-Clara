"""Asistente financiero: reglas simples y explicables sobre los datos del usuario.

Cada insight es {id, level, title, text}. level: warn (atender), info (dato útil), good (vas bien).
"""
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Account, Category, Debt, SavingsGoal, Transaction
from . import finance
from .notifications import cop
from .queries import (account_balances, budget_rows, current_month, month_bounds, month_totals,
                      prev_month, spent_by_category)

SPIKE_RATIO = 1.25
SPIKE_MIN_INCREASE = 50_000
RANK = {"warn": 0, "info": 1, "good": 2}


def _insight(id_: str, level: str, title: str, text: str) -> dict:
    return {"id": id_, "level": level, "title": title, "text": text}


def _recent_months(month: str, n: int) -> list[str]:
    out, m = [], month
    for _ in range(n):
        m = prev_month(m)
        out.append(m)
    return out


def _savings_rate(income: float, expense: float) -> list[dict]:
    if income <= 0:
        if expense > 0:
            return [_insight("no-income", "info", "Sin ingresos este mes",
                             "Registra tus ingresos para calcular cuánto estás ahorrando.")]
        return []
    rate = (income - expense) / income
    pct = round(rate * 100)
    if rate < 0:
        return [_insight("savings-rate", "warn", "Gastaste más de lo que ingresó",
                         f"Este mes llevas {cop(expense)} en gastos contra {cop(income)} de ingresos.")]
    if rate >= 0.2:
        return [_insight("savings-rate", "good", f"Estás ahorrando el {pct}% de tus ingresos",
                         f"Te quedan {cop(income - expense)} este mes. Por encima del 20% es un muy buen ritmo.")]
    if rate < 0.1:
        return [_insight("savings-rate", "warn", f"Solo te queda el {pct}% de tus ingresos",
                         "Una referencia común es ahorrar al menos 10%–20%. Revisa tus gastos más grandes.")]
    return [_insight("savings-rate", "info", f"Estás ahorrando el {pct}% de tus ingresos",
                     "Vas bien; con un poco más de ajuste llegas al 20% recomendado.")]


def _category_spikes(db: Session, user_id: int, month: str) -> list[dict]:
    cur = spent_by_category(db, user_id, *month_bounds(month))
    prev = spent_by_category(db, user_id, *month_bounds(prev_month(month)))
    names = dict(db.execute(select(Category.id, Category.name).where(Category.user_id == user_id)).all())
    spikes = []
    for cat, now_amount in cur.items():
        now, before = float(now_amount), float(prev.get(cat) or 0)
        if before > 0 and now > before * SPIKE_RATIO and now - before >= SPIKE_MIN_INCREASE:
            spikes.append((now - before, cat, now, before))
    out = []
    for _, cat, now, before in sorted(spikes, reverse=True)[:2]:
        name = names.get(cat, "Sin categoría")
        up = round((now / before - 1) * 100)
        out.append(_insight(f"spike-{cat}", "warn", f"Gastas {up}% más en {name}",
                            f"Van {cop(now)} este mes contra {cop(before)} el mes pasado."))
    return out


UNUSUAL_RATIO = 3          # una compra es «inusual» si vale 3 veces o más la compra típica de su categoría
UNUSUAL_MIN_AMOUNT = 50_000  # y no es una cifra pequeña
UNUSUAL_MIN_HISTORY = 5    # hace falta historial suficiente para saber qué es «típico»
UNUSUAL_RECENT_DAYS = 30
UNUSUAL_HISTORY_DAYS = 120


def _unusual_spending(db: Session, user_id: int, today: date) -> list[dict]:
    """Compras recientes mucho mayores que lo normal en su categoría."""
    recent_from = today - timedelta(days=UNUSUAL_RECENT_DAYS)
    base = [Transaction.user_id == user_id, Transaction.kind == "expense", Transaction.category_id.is_not(None),
            Transaction.transfer_id.is_(None), Transaction.loan_id.is_(None)]
    recent = db.scalars(select(Transaction).where(*base, Transaction.date > recent_from, Transaction.date <= today)).all()
    if not recent:
        return []
    history: dict[int, list[Decimal]] = {}
    for cat_id, amount in db.execute(select(Transaction.category_id, Transaction.amount).where(
            *base, Transaction.date <= recent_from, Transaction.date > recent_from - timedelta(days=UNUSUAL_HISTORY_DAYS))):
        history.setdefault(cat_id, []).append(amount)
    names = dict(db.execute(select(Category.id, Category.name).where(Category.user_id == user_id)).all())

    found = []
    for t in recent:
        sample = history.get(t.category_id, [])
        if len(sample) < UNUSUAL_MIN_HISTORY or t.amount < UNUSUAL_MIN_AMOUNT:
            continue
        typical = median(sample)
        if typical > 0 and t.amount >= typical * UNUSUAL_RATIO:
            found.append((float(t.amount / typical), t, typical))
    out = []
    for ratio, t, typical in sorted(found, key=lambda f: -f[0])[:2]:
        what = f"«{t.note}» " if t.note else ""
        out.append(_insight(
            f"unusual-{t.id}", "info", f"Gasto fuera de lo normal en {names.get(t.category_id, 'una categoría')}",
            f"{what}por {cop(t.amount)} el {t.date.strftime('%d/%m')} es unas {ratio:.0f} veces tu compra típica en esa "
            f"categoría ({cop(typical)}). Si no lo reconoces, revísalo."))
    return out


def _budget_summary(db: Session, user_id: int, month: str) -> list[dict]:
    rows = budget_rows(db, user_id, month)
    over = [r["category"] for r in rows if r["pct"] > 100]
    near = [r["category"] for r in rows if 80 <= r["pct"] <= 100]
    out = []
    if over:
        out.append(_insight("budget-over", "warn", "Presupuestos excedidos", ", ".join(over) + "."))
    if near:
        out.append(_insight("budget-near", "info", "Presupuestos casi agotados", ", ".join(near) + "."))
    if rows and not over and not near:
        out.append(_insight("budget-ok", "good", "Presupuestos bajo control",
                            "Ninguna categoría ha superado el 80% de su tope este mes."))
    return out


def _debt_advice(debts: list[Debt]) -> list[dict]:
    out = []
    active = [d for d in debts if d.current_balance > 0]
    for d in active:
        if d.rate <= 0:
            continue
        r = finance.monthly_rate(float(d.rate), d.rate_type)
        balance = float(d.current_balance)
        interest = balance * r
        if d.monthly_payment:
            payment = float(d.monthly_payment)
        elif d.term_months:
            payment = finance.loan_payment(balance, r, d.term_months)
        else:
            out.append(_insight(f"debt-{d.id}", "warn", f"{d.name}: define cuánto pagas al mes",
                                f"Con esa tasa generas unos {cop(interest)} de interés al mes. "
                                "Indica tu pago mensual para proyectar cuándo la terminas."))
            continue
        try:
            base = finance.amortize(balance, r, payment)
        except ValueError:
            out.append(_insight(f"debt-{d.id}", "warn", f"{d.name}: tu pago no cubre los intereses",
                                f"Solo los intereses son unos {cop(interest)} al mes y pagas {cop(payment)}: la deuda crece."))
            continue
        extra = max(50_000.0, round(payment * 0.25, -3))
        faster = finance.amortize(balance, r, payment, extra)
        out.append(_insight(
            f"debt-{d.id}", "info", f"{d.name}: pagas {cop(interest)} al mes en intereses",
            f"Con {cop(extra)} extra cada mes la terminas {base['months'] - faster['months']} meses antes "
            f"y te ahorras {cop(base['total_interest'] - faster['total_interest'])} en intereses."))
    if len(active) >= 2:
        worst = max(active, key=lambda d: finance.monthly_rate(float(d.rate), d.rate_type))
        out.append(_insight("debt-priority", "info", f"Prioriza pagar {worst.name}",
                            f"Es la deuda más cara ({worst.rate}% {worst.rate_type}). Paga el mínimo en las demás "
                            "y manda todo lo extra a esta: es lo que más intereses te ahorra."))
    return out


def _emergency_fund(cash: float, avg_expense: float) -> list[dict]:
    if avg_expense <= 0:
        return []
    months = cash / avg_expense
    text = f"Tu dinero disponible ({cop(cash)}) cubre {months:.1f} meses de tus gastos promedio ({cop(avg_expense)})."
    if months < 1:
        return [_insight("emergency", "warn", "Poco colchón de emergencia", text + " La meta recomendada son 3 a 6 meses.")]
    if months < 3:
        return [_insight("emergency", "warn", "Tu fondo de emergencia aún es corto",
                         text + " La meta recomendada son 3 a 6 meses.")]
    if months < 6:
        return [_insight("emergency", "info", "Buen avance en tu fondo de emergencia",
                         text + " Llegar a 6 meses te da más tranquilidad.")]
    return [_insight("emergency", "good", "Fondo de emergencia sólido", text)]


def _goal_advice(goals: list[SavingsGoal], avg_net: float, today: date) -> list[dict]:
    out = []
    for g in goals:
        if g.current_amount >= g.target_amount or g.target_date <= today:
            continue
        n = finance.months_between(today, g.target_date)
        r = finance.monthly_rate(float(g.annual_rate), "EA")
        needed = finance.savings_required(float(g.target_amount), float(g.current_amount), r, n)
        if avg_net <= 0:
            out.append(_insight(f"goal-{g.id}", "warn", f"Meta «{g.name}»: necesitas {cop(needed)} al mes",
                                "Tus últimos meses no dejaron ahorro; ajusta gastos o la fecha de la meta."))
        elif needed > avg_net * 0.8:
            out.append(_insight(f"goal-{g.id}", "warn", f"Meta «{g.name}»: exige {cop(needed)} al mes",
                                f"Tu ahorro promedio es {cop(avg_net)} al mes. Considera alargar la fecha o aportar más."))
        else:
            out.append(_insight(f"goal-{g.id}", "good", f"Meta «{g.name}» al alcance",
                                f"Ahorrando {cop(needed)} al mes llegas en {n} meses; tu ahorro promedio es {cop(avg_net)}."))
    return out


def insights(db: Session, user_id: int, today: date | None = None) -> list[dict]:
    today = today or clock.today()
    month = today.strftime("%Y-%m") if today else current_month()

    has_data = db.scalar(select(Transaction.id).where(Transaction.user_id == user_id).limit(1))
    if not has_data:
        return [_insight("empty", "info", "Empieza registrando tus movimientos",
                         "Agrega tus cuentas y tus primeros gastos e ingresos: con eso el asistente podrá analizar "
                         "tu mes, tus deudas y tus metas.")]

    income, expense = (float(x) for x in month_totals(db, user_id, month))
    recent = [month_totals(db, user_id, m) for m in _recent_months(month, 3)]
    expenses = [float(e) for _, e in recent if e > 0]
    avg_expense = sum(expenses) / len(expenses) if expenses else 0.0
    nets = [float(i - e) for i, e in recent if i > 0 or e > 0]
    avg_net = sum(nets) / len(nets) if nets else 0.0

    moved = account_balances(db, user_id)
    cash = float(sum(
        (a.initial_balance + (moved.get(a.id) or 0))
        for a in db.scalars(select(Account).where(Account.user_id == user_id, Account.type != "credit_card"))
    ))
    debts = db.scalars(select(Debt).where(Debt.user_id == user_id)).all()
    goals = db.scalars(select(SavingsGoal).where(SavingsGoal.user_id == user_id)).all()

    out = (
        _savings_rate(income, expense)
        + _category_spikes(db, user_id, month)
        + _unusual_spending(db, user_id, today)
        + _budget_summary(db, user_id, month)
        + _debt_advice(debts)
        + _emergency_fund(cash, avg_expense)
        + _goal_advice(goals, avg_net, today)
    )
    return sorted(out, key=lambda i: RANK[i["level"]])
