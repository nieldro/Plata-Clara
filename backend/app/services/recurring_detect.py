"""Detecta gastos e ingresos que se repiten (Netflix, arriendo, nómina…) mirando el historial."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Account, Recurring, Transaction
from .merchants import merchant_key
from .recurring import add_months

AMOUNT_TOLERANCE = Decimal("0.05")   # el monto puede variar hasta 5 % (cuotas con pequeños ajustes)
MIN_OCCURRENCES = 3
LOOKBACK_DAYS = 400
# frecuencia → (rango del tiempo entre repeticiones en días, días del período)
BANDS = {"weekly": ((6, 8), 7), "biweekly": ((13, 16), 14), "monthly": ((26, 35), 30)}


def _frequency(gaps: list[int]) -> str | None:
    gap = median(gaps)
    for name, ((lo, hi), _) in BANDS.items():
        if lo <= gap <= hi:
            inside = sum(lo <= g <= hi for g in gaps)
            return name if inside / len(gaps) >= 0.7 else None  # la mayoría debe ser regular
    return None


def _next_start(last: date, frequency: str, today: date) -> date:
    """Primera fecha futura (desde hoy) en que tocaría de nuevo. Nunca en el pasado: crear el recurrente no debe
    registrar movimientos atrasados que ya existen."""
    step_days = {"weekly": 7, "biweekly": 14}.get(frequency)  # None = mensual
    nxt = last
    for _ in range(400):
        nxt = nxt + timedelta(days=step_days) if step_days else add_months(nxt, 1, last.day)
        if nxt >= today:
            return nxt
    return today


def detect(db: Session, user_id: int, today: date | None = None) -> list[dict]:
    today = today or clock.today()
    rows = db.scalars(
        select(Transaction).where(
            Transaction.user_id == user_id, Transaction.transfer_id.is_(None), Transaction.loan_id.is_(None),
            Transaction.date >= today - timedelta(days=LOOKBACK_DAYS), Transaction.date <= today)
        .order_by(Transaction.date, Transaction.id)).all()

    groups: dict[tuple, list[Transaction]] = defaultdict(list)
    for t in rows:
        key = merchant_key(t.note)
        if key:  # sin una palabra que identifique el comercio no hay forma de agrupar con confianza
            groups[(t.account_id, t.kind, key)].append(t)

    active = db.scalars(select(Recurring).where(Recurring.user_id == user_id, Recurring.active.is_(True))).all()
    covered = [(r.account_id, r.kind, merchant_key(r.note), r.amount) for r in active]
    accounts = dict(db.execute(select(Account.id, Account.name).where(Account.user_id == user_id)).all())

    out = []
    for (account_id, kind, key), txs in groups.items():
        if len(txs) < MIN_OCCURRENCES:
            continue
        amounts = sorted(t.amount for t in txs)
        mid = amounts[len(amounts) // 2]
        if any(abs(a - mid) / mid > AMOUNT_TOLERANCE for a in amounts):
            continue
        dates = [t.date for t in txs]
        gaps = [(b - a).days for a, b in zip(dates, dates[1:], strict=False) if (b - a).days > 0]
        if len(gaps) < MIN_OCCURRENCES - 1:
            continue
        frequency = _frequency(gaps)
        if frequency is None:
            continue
        period = BANDS[frequency][1]
        if (today - dates[-1]).days > 2 * period:  # hace rato que no se repite: probablemente lo cancelaste
            continue
        if any(a == account_id and k == kind and ck == key and abs(amt - mid) / mid <= AMOUNT_TOLERANCE
               for a, k, ck, amt in covered):
            continue
        notes = Counter(t.note.strip() for t in txs if t.note.strip())
        cats = Counter(t.category_id for t in txs if t.category_id)
        out.append({
            "note": notes.most_common(1)[0][0], "key": key, "account_id": account_id,
            "account_name": accounts.get(account_id, ""), "kind": kind, "amount": mid, "frequency": frequency,
            "occurrences": len(txs), "last_date": dates[-1], "start_date": _next_start(dates[-1], frequency, today),
            "category_id": cats.most_common(1)[0][0] if cats else None,
        })
    out.sort(key=lambda s: (-s["amount"], s["note"]))
    return out
