from datetime import date
from decimal import Decimal

from app.services.budget_suggestions import round_up
from app.services.queries import prev_month
from conftest import category_id

THIS = date.today().strftime("%Y-%m")
M1 = prev_month(THIS)
M2 = prev_month(M1)
M3 = prev_month(M2)
M4 = prev_month(M3)


def spend(client, auth, account, category, amount, month, day=10):
    r = client.post("/api/transactions", headers=auth, json={"account_id": account["id"], "category_id": category,
                                                             "kind": "expense", "amount": amount, "date": f"{month}-{day:02d}"})
    assert r.status_code == 201


def suggest(client, auth, months=3):
    r = client.get("/api/budgets/suggestions", headers=auth, params={"months": months})
    assert r.status_code == 200, r.text
    return r.json()


def test_round_up_to_ten_thousand_with_a_floor():
    assert round_up(Decimal("0.01")) == 10_000 and round_up(Decimal("10000")) == 10_000
    assert round_up(Decimal("10000.01")) == 20_000 and round_up(Decimal("315000")) == 320_000


def test_average_over_the_window_and_suggested_cap(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    for month, amount in ((M1, 300_000), (M2, 360_000), (M3, 240_000)):
        spend(client, auth, bank, mercado, amount, month)
    item = suggest(client, auth)["items"][0]
    assert item["category"] == "Mercado" and float(item["average"]) == 300_000
    assert item["suggested"] == 320_000                      # 300.000 + 5 % = 315.000 → sube a 320.000
    assert item["has_budget"] is False and item["current_budget"] is None


def test_months_without_spending_pull_the_average_down(client, auth, bank):
    ocio = category_id(client, auth, "Ocio")
    spend(client, auth, bank, ocio, 300_000, M1)              # solo 1 de 3 meses
    assert float(suggest(client, auth)["items"][0]["average"]) == 100_000
    assert float(suggest(client, auth, months=1)["items"][0]["average"]) == 300_000


def test_current_month_and_older_months_do_not_count(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    spend(client, auth, bank, mercado, 999_999, THIS, day=1)  # el mes en curso está a medias
    spend(client, auth, bank, mercado, 999_999, M4)           # fuera de la ventana de 3 meses
    assert suggest(client, auth)["items"] == []
    assert len(suggest(client, auth, months=4)["items"]) == 1


def test_only_expense_categories_with_a_real_category_and_ordered_by_spend(client, auth, bank):
    mercado, ocio = category_id(client, auth, "Mercado"), category_id(client, auth, "Ocio")
    spend(client, auth, bank, mercado, 90_000, M1)
    spend(client, auth, bank, ocio, 300_000, M1)
    client.post("/api/transactions", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": 777_000, "date": f"{M1}-10"})  # sin categoría
    client.post("/api/transactions", headers=auth, json={"account_id": bank["id"], "kind": "income", "amount": 5_000_000, "date": f"{M1}-11",
                                                         "category_id": category_id(client, auth, "Salario")})
    assert [i["category"] for i in suggest(client, auth)["items"]] == ["Ocio", "Mercado"]


def test_existing_budgets_are_flagged_with_their_current_cap(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    spend(client, auth, bank, mercado, 300_000, M1)
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 250_000})
    item = suggest(client, auth)["items"][0]
    assert item["has_budget"] is True and float(item["current_budget"]) == 250_000


def test_apply_creates_updates_and_validates(client, auth, bank):
    mercado, ocio, salario = (category_id(client, auth, n) for n in ("Mercado", "Ocio", "Salario"))
    client.put(f"/api/budgets/{ocio}", headers=auth, json={"amount": 1})
    r = client.post("/api/budgets/suggestions/apply", headers=auth, json={"items": [
        {"category_id": mercado, "amount": 320_000}, {"category_id": ocio, "amount": 150_000}]})
    assert r.status_code == 200 and r.json() == {"created": 1, "updated": 1}
    got = {i["category"]: float(i["amount"]) for i in client.get("/api/budgets", headers=auth).json()["items"]}
    assert got == {"Mercado": 320_000, "Ocio": 150_000}

    def apply(items):
        return client.post("/api/budgets/suggestions/apply", headers=auth, json={"items": items})
    assert apply([{"category_id": salario, "amount": 100}]).status_code == 422          # ingreso: no se presupuesta
    assert apply([{"category_id": 9999, "amount": 100}]).status_code == 404
    assert apply([{"category_id": mercado, "amount": 0}]).status_code == 422
    assert apply([]).status_code == 422
    assert apply([{"category_id": mercado, "amount": 1}, {"category_id": mercado, "amount": 2}]).status_code == 422


def test_validation_and_privacy(client, auth, bank):
    assert client.get("/api/budgets/suggestions", headers=auth, params={"months": 0}).status_code == 422
    assert client.get("/api/budgets/suggestions", headers=auth, params={"months": 13}).status_code == 422
    assert client.get("/api/budgets/suggestions").status_code == 401
    mercado = category_id(client, auth, "Mercado")
    spend(client, auth, bank, mercado, 100_000, M1)
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/budgets/suggestions", headers=other).json()["items"] == []
    assert client.post("/api/budgets/suggestions/apply", headers=other, json={"items": [{"category_id": mercado, "amount": 5}]}).status_code == 404
