from datetime import date
from decimal import Decimal

import pytest

from app.services.quickadd import parse

TODAY = date(2026, 10, 20)


def p(text, accounts=None):
    return parse(text, TODAY, accounts)


@pytest.mark.parametrize("text,amount", [
    ("café 4500", "4500"),
    ("café 4.500", "4500"),
    ("4.500 café", "4500"),
    ("$ 12.000 taxi", "12000"),
    ("taxi 12,5", "12.5"),
    ("uber 50k", "50000"),
    ("uber 50 mil", "50000"),
    ("arriendo 1.300.000", "1300000"),
    ("arriendo 1,3 millones", "1300000"),
    ("arriendo 2 millones", "2000000"),
    ("mercado 1.234.567,89", "1234567.89"),
])
def test_amount_formats(text, amount):
    assert p(text).amount == Decimal(amount)


def test_picks_the_money_among_several_numbers():
    assert p("éxito calle 80 45.000").amount == Decimal(45000)       # el 80 es la dirección
    assert p("cena 20 mil mesa 5").amount == Decimal(20000)          # «mil» delata que es plata
    assert p("comida en la 80 por $30.000").amount == Decimal(30000)  # el signo $ manda


def test_note_is_what_remains_and_amount_is_not_in_it():
    r = p("café 4.500")
    assert r.note == "café" and r.amount == Decimal(4500)
    assert p("Almuerzo ejecutivo $ 18.000").note == "Almuerzo ejecutivo"


@pytest.mark.parametrize("text,expected", [
    ("café 4500", date(2026, 10, 20)),
    ("café 4500 hoy", date(2026, 10, 20)),
    ("café 4500 ayer", date(2026, 10, 19)),
    ("café 4500 anteayer", date(2026, 10, 18)),
    ("café 4500 antier", date(2026, 10, 18)),
    ("café 4500 hace 3 días", date(2026, 10, 17)),
    ("café 4500 15/10", date(2026, 10, 15)),
    ("café 4500 15/10/2026", date(2026, 10, 15)),
    ("café 4500 15-10-26", date(2026, 10, 15)),
    ("café 4500 25/12", date(2025, 12, 25)),      # diciembre aún no llega: es el del año pasado
])
def test_dates(text, expected):
    assert p(text).when == expected


def test_date_numbers_are_not_mistaken_for_the_amount():
    r = p("café 15/10 4500")
    assert r.amount == Decimal(4500) and r.when == date(2026, 10, 15) and r.note == "café"


def test_invalid_date_warns_and_falls_back_to_today():
    r = p("café 4500 31/02")
    assert r.when == TODAY and any("No entendí la fecha" in w for w in r.warnings)


def test_income_detection():
    for text in ("nómina 3.000.000", "me pagaron 200 mil", "reembolso 50.000", "+ 50.000 venta", "ingreso 100k"):
        assert p(text).kind == "income", text
    for text in ("café 4500", "pago de nómina a empleada 500000".replace("nómina", "luz")):
        assert p(text).kind == "expense", text


def test_tags_are_extracted_and_removed_from_the_note():
    r = p("cena 80.000 #Viaje-Cartagena #comida")
    assert r.tags == ["viaje-cartagena", "comida"] and r.note == "cena" and r.amount == Decimal(80000)
    assert p("#2026 café 4500").amount == Decimal(4500)   # un número en una etiqueta no es el monto


def test_account_is_recognised_by_name():
    accounts = {"nequi": 1, "bancolombia": 2, "ahorros nomina": 3}
    r = p("café 4500 con nequi", accounts)
    assert r.account_hint == "nequi" and r.note == "café"
    assert p("mercado 80000 en Bancolombia", accounts).account_hint == "bancolombia"
    assert p("mercado 80000 desde mi ahorros nómina", accounts).account_hint == "ahorros nomina"
    assert p("café 4500", accounts).account_hint is None
    assert p("café nequi 4500", accounts).account_hint is None  # sin «con/en/desde» no se asume


def test_missing_amount_and_empty_input():
    r = p("solo una nota")
    assert r.amount is None and any("monto" in w for w in r.warnings) and r.note == "solo una nota"
    assert p("").amount is None and p("   ").warnings
    assert p("café 0").amount is None


def test_huge_amounts_and_future_dates_are_flagged():
    assert p("casa 99.999.999.999.999").amount is None
    assert any("futura" in w for w in p("café 4500 21/10").warnings)      # mañana: se respeta, pero se avisa
    assert p("café 4500 25/10").when == date(2025, 10, 25)               # más lejos y sin año: es el del año pasado
    assert any("futura" in w for w in p("café 4500 25/10/2026").warnings)  # con año explícito se respeta y se avisa


def test_full_sentence():
    r = p("Almuerzo con el equipo 85.000 ayer con nequi #trabajo", {"nequi": 7})
    assert (r.amount, r.when, r.account_hint, r.tags, r.kind) == (Decimal(85000), date(2026, 10, 19), "nequi", ["trabajo"], "expense")
    assert r.note == "Almuerzo con el equipo"
