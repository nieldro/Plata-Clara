"""Entiende un gasto escrito en lenguaje natural: «café 4.500 ayer con nequi #trabajo».

Es un intérprete de reglas (sin IA): saca monto, tipo, fecha, etiquetas y la cuenta, y el resto queda como nota.
Nunca guarda nada: devuelve una propuesta que el usuario revisa antes de crear el movimiento.
"""
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from .importer import parse_amount, parse_date
from .rules import fold

MAX_AMOUNT = Decimal("999999999999")
INCOME_WORDS = {"ingreso", "ingrese", "cobre", "recibi", "nomina", "salario", "reembolso", "devolucion", "me pagaron",
                "me consignaron", "me abonaron", "me devolvieron"}
RELATIVE_DAYS = {"hoy": 0, "ayer": 1, "anteayer": 2, "antier": 2}

DATE_RE = re.compile(r"(?<![\w/.])(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?(?![\w/])")
AGO_RE = re.compile(r"\bhace\s+(\d{1,3})\s+d[ií]as?\b", re.I)
TAG_RE = re.compile(r"(?<!\w)#([\w-]{1,30})")
NUM_RE = re.compile(
    r"(?<![\w/.,])(\$?)\s?(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s?(millones|millon|mil|k|m)?(?![\w/])", re.I)
SUFFIX = {"k": 1_000, "mil": 1_000, "m": 1_000_000, "millon": 1_000_000, "millones": 1_000_000}


@dataclass
class Parsed:
    amount: Decimal | None = None
    kind: str = "expense"
    when: date | None = None
    note: str = ""
    tags: list[str] = field(default_factory=list)
    account_hint: str | None = None
    warnings: list[str] = field(default_factory=list)


def _cut(text: str, spans: list[tuple[int, int]]) -> str:
    for a, b in sorted(spans, reverse=True):
        text = text[:a] + " " + text[b:]
    return re.sub(r"\s+", " ", text).strip(" ,.;:-")


def _find_amount(text: str) -> tuple[Decimal, tuple[int, int]] | None:
    best = None
    for m in NUM_RE.finditer(text):
        value = parse_amount(m.group(2))
        if value is None or value <= 0:
            continue
        suffix = (m.group(3) or "").lower()
        if suffix:
            value *= SUFFIX[suffix]
        priority = 2 if (m.group(1) or suffix) else 1  # con «$» o «mil/k/millones» se nota que es plata
        key = (priority, value)
        if best is None or key > best[0]:
            best = (key, value, m.span())
    return (best[1], best[2]) if best else None


def parse(text: str, today: date, account_names: dict[str, int] | None = None) -> Parsed:
    """`account_names`: nombre (ya sin tildes y en minúsculas) → id de cuenta, para reconocer «con nequi»."""
    original = (text or "").strip()
    out = Parsed()
    if not original:
        out.warnings.append("Escribe algo, por ejemplo: café 4.500 ayer")
        return out
    folded = fold(original)
    if len(folded) != len(original):  # no debería pasar; si pasa, se trabaja sin tildes para no desalinear posiciones
        original = folded
    spans: list[tuple[int, int]] = []

    # etiquetas
    for m in TAG_RE.finditer(original):
        tag = m.group(1).lower()
        if tag not in out.tags:
            out.tags.append(tag)
        spans.append(m.span())

    # fecha: explícita, «hace N días» o palabra
    ago = AGO_RE.search(original)
    explicit = DATE_RE.search(original)
    if explicit:
        d, mth, year = explicit.group(1), explicit.group(2), explicit.group(3)
        guess = parse_date(f"{d}/{mth}/{year}" if year else f"{d}/{mth}/{today.year}")
        if guess and not year and guess > today + timedelta(days=1):
            guess = parse_date(f"{d}/{mth}/{today.year - 1}")  # «25/12» en octubre es el diciembre pasado
        if guess:
            out.when = guess
            spans.append(explicit.span())
        else:
            out.warnings.append(f"No entendí la fecha «{explicit.group(0)}»; se usará hoy")
    elif ago:
        out.when = today - timedelta(days=int(ago.group(1)))
        spans.append(ago.span())
    else:
        for word, back in RELATIVE_DAYS.items():
            m = re.search(rf"\b{word}\b", folded)
            if m:
                out.when = today - timedelta(days=back)
                spans.append(m.span())
                break
    out.when = out.when or today
    if out.when > today:
        out.warnings.append("La fecha es futura")

    # monto (se busca sin las fechas y etiquetas, para no confundir «12/10» ni «#2026» con plata)
    masked = original
    for a, b in spans:
        masked = masked[:a] + " " * (b - a) + masked[b:]
    found = _find_amount(masked)
    if found:
        out.amount, span = found
        if out.amount > MAX_AMOUNT:
            out.amount = None
            out.warnings.append("El monto es demasiado grande")
        spans.append(span)
    else:
        out.warnings.append("No encontré el monto: escribe un número, por ejemplo 4.500 o 50 mil")

    # tipo
    padded = f" {folded} "
    if folded.lstrip().startswith("+") or any(f" {w} " in padded for w in INCOME_WORDS):
        out.kind = "income"

    # cuenta: «con nequi», «en bancolombia», «desde ahorros»
    if account_names:
        for name in sorted(account_names, key=len, reverse=True):
            m = re.search(rf"\b(?:con|en|desde|de|por)\s+(?:la\s+|el\s+|mi\s+)?{re.escape(name)}\b", folded)
            if m:
                out.account_hint = name
                spans.append(m.span())
                break

    out.note = _cut(original, spans)
    return out
