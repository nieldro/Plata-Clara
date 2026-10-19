def card(client, auth, **extra):
    body = {"name": "Visa", "type": "credit_card", "institution": "davivienda", "initial_balance": 500_000,
            "credit_limit": 2_000_000, "rate": 28, "rate_type": "EA", "monthly_payment": 100_000, "due_day": 15, **extra}
    r = client.post("/api/accounts", headers=auth, json=body)
    assert r.status_code == 201
    return r.json()


def patch(client, auth, account, **changes):
    return client.patch(f"/api/accounts/{account['id']}", headers=auth, json=changes)


def test_rename_and_fix_opening_balance(client, auth, bank):
    r = patch(client, auth, bank, name="  Nómina  ", initial_balance=1_250_000)
    assert r.status_code == 200 and r.json()["name"] == "Nómina"
    assert float(r.json()["balance"]) == 1_250_000  # el saldo se recalcula con el nuevo saldo inicial


def test_balance_keeps_counting_movements_after_edit(client, auth, bank):
    client.post("/api/transactions", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": 50_000, "date": "2026-03-01"})
    r = patch(client, auth, bank, initial_balance=2_000_000)
    assert float(r.json()["balance"]) == 1_950_000


def test_card_limit_rate_payment_and_due_day_are_editable(client, auth):
    c = card(client, auth)
    r = patch(client, auth, c, credit_limit=3_000_000, rate=30, monthly_payment=250_000, due_day=20)
    assert r.status_code == 200
    assert float(r.json()["credit_limit"]) == 3_000_000 and float(r.json()["available"]) == 2_500_000
    debt = client.get("/api/debts", headers=auth).json()[0]
    assert float(debt["rate"]) == 30 and float(debt["monthly_payment"]) == 250_000 and debt["due_day"] == 20


def test_renaming_a_card_renames_its_debt_too(client, auth):
    c = card(client, auth)
    patch(client, auth, c, name="Visa Gold")
    assert client.get("/api/debts", headers=auth).json()[0]["name"] == "Davivienda · Visa Gold"


def test_optional_fields_can_be_cleared_with_null(client, auth):
    c = card(client, auth)
    assert patch(client, auth, c, monthly_payment=None, due_day=None).status_code == 200
    debt = client.get("/api/debts", headers=auth).json()[0]
    assert debt["monthly_payment"] is None and debt["due_day"] is None


def test_card_fields_on_a_regular_account_are_rejected(client, auth, bank):
    for field, value in (("credit_limit", 1000), ("rate", 5), ("monthly_payment", 10), ("due_day", 5)):
        assert patch(client, auth, bank, **{field: value}).status_code == 422


def test_card_opening_balance_cannot_be_edited(client, auth):
    assert patch(client, auth, card(client, auth), initial_balance=0).status_code == 422


def test_validation_of_values(client, auth, bank):
    assert patch(client, auth, bank, name="   ").status_code == 422
    assert patch(client, auth, bank, name=None).status_code == 422
    assert patch(client, auth, bank, initial_balance=None).status_code == 422
    c = card(client, auth)
    assert patch(client, auth, c, credit_limit=0).status_code == 422
    assert patch(client, auth, c, credit_limit=None).status_code == 422
    assert patch(client, auth, c, due_day=32).status_code == 422
    assert patch(client, auth, c, rate=-1).status_code == 422
    assert patch(client, auth, c, rate_type="XX").status_code == 422


def test_empty_patch_changes_nothing_and_ownership_is_enforced(client, auth, bank):
    assert patch(client, auth, bank).json()["name"] == "Ahorros"
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    assert client.patch(f"/api/accounts/{bank['id']}", headers=other, json={"name": "hack"}).status_code == 404
    assert client.patch("/api/accounts/9999", headers=auth, json={"name": "x"}).status_code == 404
    assert client.patch(f"/api/accounts/{bank['id']}", json={"name": "x"}).status_code == 401
