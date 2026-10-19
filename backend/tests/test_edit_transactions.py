from app.clock import today as clock_today

from conftest import category_id


def add(client, auth, account, kind="expense", amount=10_000, **extra):
    r = client.post("/api/transactions", headers=auth, json={
        "account_id": account["id"], "kind": kind, "amount": amount,
        "date": clock_today().isoformat(), **extra})
    assert r.status_code == 201
    return r.json()


def balance(client, auth, name):
    return float(next(a for a in client.get("/api/accounts", headers=auth).json() if a["name"] == name)["balance"])


def test_edit_amount_updates_balance(client, auth, bank):
    tx = add(client, auth, bank, amount=10_000)
    r = client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"amount": 25_000, "note": "corregido"})
    assert r.status_code == 200 and float(r.json()["amount"]) == 25_000 and r.json()["note"] == "corregido"
    assert balance(client, auth, "Ahorros") == 1_000_000 - 25_000


def test_edit_changes_kind_and_category(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    tx = add(client, auth, bank, amount=50_000)
    client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"category_id": mercado, "kind": "income"})
    assert balance(client, auth, "Ahorros") == 1_050_000
    got = client.get("/api/transactions", headers=auth).json()[0]
    assert got["category_id"] == mercado and got["kind"] == "income"
    client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"clear_category": True})
    assert client.get("/api/transactions", headers=auth).json()[0]["category_id"] is None


def test_edit_moves_between_accounts(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={
        "name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    tx = add(client, auth, bank, amount=40_000)
    client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"account_id": other["id"]})
    assert balance(client, auth, "Ahorros") == 1_000_000
    assert balance(client, auth, "Nequi") == -40_000


def test_edit_card_purchase_recalculates_debt(client, auth):
    card = client.post("/api/accounts", headers=auth, json={
        "name": "Visa", "type": "credit_card", "institution": "davivienda",
        "initial_balance": 100_000, "credit_limit": 2_000_000}).json()
    tx = add(client, auth, card, amount=30_000)  # deuda 130k
    client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"amount": 80_000})
    assert float(client.get("/api/debts", headers=auth).json()[0]["current_balance"]) == 180_000
    client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"kind": "income"})  # ahora es un abono
    assert float(client.get("/api/debts", headers=auth).json()[0]["current_balance"]) == 20_000


def test_cannot_edit_transfer_or_foreign_transaction(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={
        "name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    client.post("/api/transfers", headers=auth, json={
        "from_account_id": bank["id"], "to_account_id": other["id"], "amount": 5, "date": clock_today().isoformat()})
    leg = client.get("/api/transactions", headers=auth).json()[0]
    assert client.patch(f"/api/transactions/{leg['id']}", headers=auth, json={"amount": 9}).status_code == 422

    tx = add(client, auth, bank)
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    hacker = {"Authorization": f"Bearer {tok}"}
    assert client.patch(f"/api/transactions/{tx['id']}", headers=hacker, json={"amount": 1}).status_code == 404
    assert client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"account_id": 9999}).status_code == 404
