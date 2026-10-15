from datetime import date

from conftest import category_id


def accounts(client, auth):
    return {a["name"]: a for a in client.get("/api/accounts", headers=auth).json()}


def make_card(client, auth, debt=500_000):
    return client.post("/api/accounts", headers=auth, json={
        "name": "Visa", "type": "credit_card", "institution": "davivienda",
        "initial_balance": debt, "credit_limit": 2_000_000,
    }).json()


def transfer(client, auth, src, dst, amount):
    return client.post("/api/transfers", headers=auth, json={
        "from_account_id": src["id"], "to_account_id": dst["id"], "amount": amount,
        "date": date.today().isoformat(),
    })


def test_transfer_moves_money_between_accounts(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={
        "name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    assert transfer(client, auth, bank, other, 250_000).status_code == 201
    got = accounts(client, auth)
    assert float(got["Ahorros"]["balance"]) == 750_000
    assert float(got["Nequi"]["balance"]) == 250_000


def test_transfer_is_not_income_or_expense(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={
        "name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    transfer(client, auth, bank, other, 100_000)
    month = date.today().strftime("%Y-%m")
    s = client.get(f"/api/summary?month={month}", headers=auth).json()
    assert float(s["income"]) == 0 and float(s["expense"]) == 0
    t = client.get("/api/summary/trend?months=1", headers=auth).json()[0]
    assert t["income"] == 0 and t["expense"] == 0


def test_transfer_to_card_pays_debt(client, auth, bank):
    card = make_card(client, auth, 500_000)
    transfer(client, auth, bank, card, 200_000)
    got = accounts(client, auth)
    assert float(got["Ahorros"]["balance"]) == 800_000
    assert float(got["Visa"]["balance"]) == -300_000


def test_deleting_one_leg_removes_both_and_reverts(client, auth, bank):
    card = make_card(client, auth, 500_000)
    transfer(client, auth, bank, card, 200_000)
    legs = client.get("/api/transactions", headers=auth).json()
    assert len(legs) == 2 and legs[0]["transfer_id"] == legs[1]["transfer_id"]
    assert client.delete(f"/api/transactions/{legs[0]['id']}", headers=auth).status_code == 204
    assert client.get("/api/transactions", headers=auth).json() == []
    got = accounts(client, auth)
    assert float(got["Ahorros"]["balance"]) == 1_000_000
    assert float(got["Visa"]["balance"]) == -500_000


def test_transfer_validations(client, auth, bank):
    assert transfer(client, auth, bank, bank, 10).status_code == 422
    assert client.post("/api/transfers", headers=auth, json={
        "from_account_id": bank["id"], "to_account_id": 999, "amount": 10, "date": date.today().isoformat(),
    }).status_code == 404


def test_delete_category_keeps_transactions(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 100_000})
    client.post("/api/transactions", headers=auth, json={
        "account_id": bank["id"], "category_id": mercado, "kind": "expense", "amount": 5_000,
        "date": date.today().isoformat()})
    assert client.delete(f"/api/categories/{mercado}", headers=auth).status_code == 204
    tx = client.get("/api/transactions", headers=auth).json()[0]
    assert tx["category_id"] is None
    assert client.get("/api/budgets", headers=auth).json()["items"] == []


def test_create_custom_category(client, auth):
    r = client.post("/api/categories", headers=auth, json={"name": "Mascotas", "kind": "expense"})
    assert r.status_code == 201
    assert "Mascotas" in [c["name"] for c in client.get("/api/categories", headers=auth).json()]
