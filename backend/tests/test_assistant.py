from datetime import date, timedelta

from app.services.queries import prev_month
from conftest import category_id


def tx(client, auth, account, kind, amount, day=None, category=None):
    r = client.post("/api/transactions", headers=auth, json={
        "account_id": account["id"], "category_id": category, "kind": kind, "amount": amount,
        "date": (day or date.today()).isoformat(),
    })
    assert r.status_code == 201


def ask(client, auth):
    return {i["id"]: i for i in client.get("/api/assistant", headers=auth).json()["insights"]}


def test_empty_account_gets_onboarding_tip(client, auth):
    got = ask(client, auth)
    assert list(got) == ["empty"]


def test_savings_rate_good_and_negative(client, auth, bank):
    tx(client, auth, bank, "income", 1_000_000)
    tx(client, auth, bank, "expense", 500_000)
    assert ask(client, auth)["savings-rate"]["level"] == "good"

    tx(client, auth, bank, "expense", 900_000)
    assert ask(client, auth)["savings-rate"]["level"] == "warn"


def test_category_spike_vs_last_month(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    last = date.fromisoformat(prev_month(date.today().strftime("%Y-%m")) + "-10")
    tx(client, auth, bank, "expense", 100_000, last, mercado)
    tx(client, auth, bank, "expense", 300_000, None, mercado)
    spikes = [i for k, i in ask(client, auth).items() if k.startswith("spike-")]
    assert len(spikes) == 1 and "200%" in spikes[0]["title"] and "Mercado" in spikes[0]["title"]


def test_debt_advice_with_extra_payment_savings(client, auth):
    client.post("/api/accounts", headers=auth, json={
        "name": "Visa", "type": "credit_card", "institution": "davivienda", "initial_balance": 3_000_000,
        "credit_limit": 6_000_000, "rate": 28, "rate_type": "EA", "monthly_payment": 200_000,
    })
    got = ask(client, auth)  # sin movimientos aún → solo onboarding
    assert "empty" in got

    bank = client.post("/api/accounts", headers=auth, json={
        "name": "Ahorros", "type": "savings", "institution": "bancolombia", "initial_balance": 0}).json()
    tx(client, auth, bank, "income", 1_000_000)
    debt = next(i for k, i in ask(client, auth).items() if k.startswith("debt-") and k != "debt-priority")
    assert debt["level"] == "info" and "meses antes" in debt["text"]


def test_payment_below_interest_warns(client, auth, bank):
    tx(client, auth, bank, "income", 100_000)
    client.post("/api/accounts", headers=auth, json={
        "name": "Tarjeta", "type": "credit_card", "institution": "bbva", "initial_balance": 2_000_000,
        "rate": 30, "rate_type": "EA", "monthly_payment": 10_000,
    })
    debt = next(i for k, i in ask(client, auth).items() if k.startswith("debt-"))
    assert debt["level"] == "warn" and "no cubre" in debt["title"]


def test_highest_rate_debt_is_prioritised(client, auth, bank):
    tx(client, auth, bank, "income", 100_000)
    for name, rate in (("Barata", 12), ("Cara", 40)):
        client.post("/api/debts", headers=auth, json={
            "name": name, "kind": "loan", "original_amount": 1_000_000, "current_balance": 1_000_000,
            "rate": rate, "rate_type": "EA", "term_months": 12,
        })
    assert "Cara" in ask(client, auth)["debt-priority"]["title"]


def test_emergency_fund_coverage(client, auth):
    acc = client.post("/api/accounts", headers=auth, json={
        "name": "Ahorros", "type": "savings", "institution": "bancolombia", "initial_balance": 3_000_000}).json()
    month = date.today().strftime("%Y-%m")
    for _ in range(3):
        month = prev_month(month)
        tx(client, auth, acc, "expense", 500_000, date.fromisoformat(month + "-10"))
    em = ask(client, auth)["emergency"]
    assert "3.0 meses" in em["text"] and em["level"] == "info"


def test_goal_too_ambitious_warns(client, auth, bank):
    tx(client, auth, bank, "income", 100_000)
    client.post("/api/savings", headers=auth, json={
        "name": "Carro", "target_amount": 50_000_000, "target_date": (date.today() + timedelta(days=365)).isoformat(),
    })
    goal = next(i for k, i in ask(client, auth).items() if k.startswith("goal-"))
    assert goal["level"] == "warn"


def test_warnings_come_first(client, auth, bank):
    tx(client, auth, bank, "income", 1_000_000)
    tx(client, auth, bank, "expense", 1_500_000)
    levels = [i["level"] for i in client.get("/api/assistant", headers=auth).json()["insights"]]
    assert levels == sorted(levels, key={"warn": 0, "info": 1, "good": 2}.get)
