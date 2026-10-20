from app.clock import today as clock_today
from conftest import category_id


def add(client, auth, account, amount, day, kind="expense", category=None):
    r = client.post("/api/transactions", headers=auth, json={"account_id": account["id"], "kind": kind, "amount": amount,
                                                             "date": day, "category_id": category})
    assert r.status_code == 201


def annual(client, auth, **params):
    r = client.get("/api/insights/annual", headers=auth, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def seed(client, auth, bank):
    mercado, ocio = category_id(client, auth, "Mercado"), category_id(client, auth, "Ocio")
    add(client, auth, bank, 4_000_000, "2025-01-05", "income")
    add(client, auth, bank, 1_000_000, "2025-01-10", category=mercado)
    add(client, auth, bank, 4_000_000, "2025-03-05", "income")
    add(client, auth, bank, 3_500_000, "2025-03-20", category=ocio)
    add(client, auth, bank, 500_000, "2025-03-21", category=mercado)
    add(client, auth, bank, 999, "2024-12-31")      # de otro año: no cuenta
    add(client, auth, bank, 999, "2026-01-01")


def test_year_totals_months_and_derived_numbers(client, auth, bank):
    seed(client, auth, bank)
    a = annual(client, auth, year=2025)
    assert a["year"] == 2025 and len(a["months"]) == 12
    assert float(a["income"]) == 8_000_000 and float(a["expense"]) == 5_000_000 and float(a["net"]) == 3_000_000
    assert a["savings_rate"] == 37.5 and a["active_months"] == 2
    assert float(a["avg_monthly_expense"]) == 2_500_000
    assert a["best_month"] == "2025-01" and a["worst_month"] == "2025-03"
    jan, feb, mar = a["months"][0], a["months"][1], a["months"][2]
    assert (float(jan["income"]), float(jan["expense"]), float(jan["net"])) == (4_000_000, 1_000_000, 3_000_000)
    assert float(feb["income"]) == 0 and float(mar["net"]) == 0 - 0 + 4_000_000 - 4_000_000


def test_top_categories_are_ranked_with_percentages(client, auth, bank):
    seed(client, auth, bank)
    cats = annual(client, auth, year=2025)["top_categories"]
    assert [c["category"] for c in cats] == ["Ocio", "Mercado"]
    assert float(cats[0]["total"]) == 3_500_000 and cats[0]["pct"] == 70.0 and cats[1]["pct"] == 30.0


def test_defaults_to_the_current_year_and_handles_empty_years(client, auth, bank):
    assert annual(client, auth)["year"] == clock_today().year
    empty = annual(client, auth, year=2010)
    assert empty["active_months"] == 0 and empty["best_month"] is None and empty["savings_rate"] is None
    assert float(empty["avg_monthly_expense"]) == 0 and empty["top_categories"] == []


def test_transfers_and_loans_do_not_count(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={"name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    client.post("/api/transfers", headers=auth, json={"from_account_id": bank["id"], "to_account_id": other["id"], "amount": 777, "date": "2025-05-05"})
    client.post("/api/loans", headers=auth, json={"person": "Ana", "direction": "lent", "amount": 555, "date": "2025-05-06", "account_id": bank["id"]})
    a = annual(client, auth, year=2025)
    assert float(a["income"]) == 0 and float(a["expense"]) == 0


def test_expenses_without_income_have_no_savings_rate(client, auth, bank):
    add(client, auth, bank, 100, "2025-06-01")
    a = annual(client, auth, year=2025)
    assert a["savings_rate"] is None and a["worst_month"] == "2025-06"


def test_validation_and_privacy(client, auth, bank):
    seed(client, auth, bank)
    assert client.get("/api/insights/annual", headers=auth, params={"year": 1999}).status_code == 422
    assert client.get("/api/insights/annual", headers=auth, params={"year": "abc"}).status_code == 422
    assert client.get("/api/insights/annual").status_code == 401
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    assert float(annual(client, {"Authorization": f"Bearer {tok}"}, year=2025)["income"]) == 0
