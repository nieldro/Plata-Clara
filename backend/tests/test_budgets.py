from app.clock import today as clock_today

from conftest import category_id


def spend(client, auth, account, category, amount):
    return client.post("/api/transactions", headers=auth, json={
        "account_id": account["id"], "category_id": category, "kind": "expense",
        "amount": amount, "date": clock_today().isoformat(),
    })


def test_budget_tracks_spending(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    assert client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 500_000}).status_code == 200
    spend(client, auth, bank, mercado, 200_000)

    items = client.get("/api/budgets", headers=auth).json()["items"]
    assert len(items) == 1
    assert items[0]["category"] == "Mercado"
    assert items[0]["spent"] == 200_000
    assert items[0]["remaining"] == 300_000
    assert items[0]["pct"] == 40.0


def test_budget_update_does_not_duplicate(client, auth):
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 100_000})
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 250_000})
    items = client.get("/api/budgets", headers=auth).json()["items"]
    assert [i["amount"] for i in items] == [250_000]


def test_income_category_cannot_have_budget(client, auth):
    salario = category_id(client, auth, "Salario")
    r = client.put(f"/api/budgets/{salario}", headers=auth, json={"amount": 100})
    assert r.status_code == 422


def test_budget_delete_and_ownership(client, auth):
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 100_000})
    assert client.delete(f"/api/budgets/{mercado}", headers=auth).status_code == 204
    assert client.get("/api/budgets", headers=auth).json()["items"] == []
    assert client.delete(f"/api/budgets/{mercado}", headers=auth).status_code == 404

    # otro usuario no puede tocar categorías ajenas
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    r = client.put(f"/api/budgets/{mercado}", headers={"Authorization": f"Bearer {tok}"}, json={"amount": 1})
    assert r.status_code == 404
