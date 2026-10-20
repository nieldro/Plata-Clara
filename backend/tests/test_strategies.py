import pytest

from app.services import finance
from app.services.strategies import DebtState, compare, minimum_payment, simulate


def debt(client, auth, name, balance, rate, payment=None, term=None):
    body = {"name": name, "kind": "loan", "original_amount": balance, "current_balance": balance, "rate": rate, "rate_type": "EA"}
    if payment:
        body["monthly_payment"] = payment
    if term:
        body["term_months"] = term
    r = client.post("/api/debts", headers=auth, json=body)
    assert r.status_code == 201
    return r.json()


def strategies(client, auth, extra=0):
    r = client.get("/api/debts/strategies", headers=auth, params={"extra": extra})
    assert r.status_code == 200, r.text
    return r.json()


def state(i, name, balance, rate_ea, minimum):
    return DebtState(i, name, balance, finance.monthly_rate(rate_ea, "EA"), minimum)


# ---- el motor
def test_single_debt_matches_the_amortization_table():
    r = finance.monthly_rate(30, "EA")
    d = state(1, "Visa", 1_000_000, 30, 100_000)
    ours = simulate([d], 100_000, order=lambda x: x.balance)
    theirs = finance.amortize(1_000_000, r, 100_000)
    assert ours["months"] == theirs["months"] and ours["total_interest"] == pytest.approx(theirs["total_interest"], abs=1)


def test_avalanche_never_pays_more_interest_than_snowball():
    for extra in (0, 50_000, 200_000, 1_000_000):
        debts = [state(1, "Cara", 2_000_000, 45, 90_000), state(2, "Barata", 400_000, 8, 30_000), state(3, "Media", 900_000, 24, 50_000)]
        out = compare(debts, extra)
        assert out["avalanche"]["total_interest"] <= out["snowball"]["total_interest"] + 0.01
        assert out["avalanche"]["finished"] and out["snowball"]["finished"]


def test_priority_order_differs_between_strategies():
    debts = [state(1, "Grande y cara", 3_000_000, 50, 100_000), state(2, "Chica y barata", 200_000, 5, 20_000)]
    out = compare(debts, 150_000)
    assert out["snowball"]["order"][0]["name"] == "Chica y barata"   # bola de nieve: la de menor saldo
    assert out["avalanche"]["order"][0]["name"] == "Chica y barata"  # se salda primero por ser tan chica,
    assert out["avalanche"]["total_interest"] < out["snowball"]["total_interest"]  # pero la avalancha ataca antes la cara


def test_extra_payment_speeds_things_up_and_beats_minimums_only():
    debts = [state(1, "A", 1_500_000, 35, 60_000), state(2, "B", 700_000, 20, 35_000)]
    slow, fast = compare(debts, 0), compare(debts, 200_000)
    assert fast["avalanche"]["months"] < slow["avalanche"]["months"]
    assert fast["avalanche"]["total_interest"] < slow["avalanche"]["total_interest"]
    assert slow["avalanche"]["total_interest"] <= slow["minimums_only"]["total_interest"]  # reasignar mínimos ayuda


def test_minimums_that_do_not_cover_interest_never_finish():
    out = compare([state(1, "Trampa", 5_000_000, 40, 10_000)], 0)
    assert out["avalanche"]["finished"] is False and out["avalanche"]["months"] is None


def test_minimum_payment_rules():
    r = finance.monthly_rate(28, "EA")
    assert minimum_payment(1_000_000, r, 80_000, None) == 80_000                       # el que declaró el usuario
    assert minimum_payment(1_000_000, r, None, 12) == pytest.approx(finance.loan_payment(1_000_000, r, 12))
    assert minimum_payment(1_000_000, r, None, None) == pytest.approx(1_000_000 * r + 10_000)  # tarjeta sin datos


# ---- la API
def test_api_compares_and_recommends(client, auth):
    debt(client, auth, "Tarjeta cara", 2_000_000, 45, payment=90_000)
    debt(client, auth, "Crédito barato", 400_000, 8, payment=30_000)
    out = strategies(client, auth, extra=100_000)
    assert out["monthly_budget"] == 220_000 and out["minimums_total"] == 120_000
    assert out["avalanche"]["finished"] and out["snowball"]["finished"]
    assert out["interest_saved_by_avalanche"] >= 0 and out["recommended"] in ("avalanche", "snowball")
    assert {d["name"] for d in out["debts"]} == {"Tarjeta cara", "Crédito barato"}
    assert out["avalanche"]["months"] <= out["minimums_only"]["months"] or out["minimums_only"]["months"] is None


def test_api_ignores_paid_off_debts_and_handles_unfinishable_plans(client, auth):
    debt(client, auth, "Saldada", 100, 0, payment=100)  # sin interés: un pago de 100 la deja exactamente en cero
    client.post("/api/debts/1/payments", headers=auth, json={"amount": 100, "date": "2026-03-01"})
    assert client.get("/api/debts/strategies", headers=auth).status_code == 422          # nada con saldo que comparar
    debt(client, auth, "Trampa", 5_000_000, 40, payment=10_000)
    out = strategies(client, auth)
    assert out["avalanche"]["finished"] is False and out["interest_saved_by_avalanche"] is None
    assert [d["name"] for d in out["debts"]] == ["Trampa"]


def test_api_validation_and_privacy(client, auth):
    debt(client, auth, "Mía", 1_000_000, 20, payment=80_000)
    assert client.get("/api/debts/strategies", headers=auth, params={"extra": -1}).status_code == 422
    assert client.get("/api/debts/strategies").status_code == 401
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    assert client.get("/api/debts/strategies", headers={"Authorization": f"Bearer {tok}"}).status_code == 422  # no ve la mía
