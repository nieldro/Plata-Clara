from app.clock import today as clock_today
from app.services.merchants import merchant_key
from app.services.queries import prev_month

TODAY = clock_today()
MONTH = TODAY.strftime("%Y-%m")


def add(client, auth, account, amount, note, day=None, kind="expense"):
    r = client.post("/api/transactions", headers=auth, json={"account_id": account["id"], "kind": kind, "amount": amount,
                                                             "note": note, "date": day or TODAY.isoformat()})
    assert r.status_code == 201


def merchants(client, auth, **params):
    r = client.get("/api/insights/merchants", headers=auth, params=params)
    assert r.status_code == 200
    return r.json()


def test_merchant_key_ignores_accents_case_numbers_and_noise():
    assert merchant_key("Éxito Calle 80") == merchant_key("EXITO chapinero") == "exito"
    assert merchant_key("Compra PSE Rappi 123") == "rappi"        # «compra» y «pse» no son el comercio
    assert merchant_key("") == "" and merchant_key(None) == "" and merchant_key("12 34") == ""


def test_groups_variants_of_the_same_merchant(client, auth, bank):
    add(client, auth, bank, 50_000, "Éxito Calle 80")
    add(client, auth, bank, 30_000, "EXITO chapinero")
    add(client, auth, bank, 20_000, "Éxito Calle 80")
    add(client, auth, bank, 10_000, "Rappi")
    data = merchants(client, auth)
    assert [i["name"] for i in data["items"]] == ["Éxito", "Rappi"]
    assert data["items"][0]["count"] == 3 and float(data["items"][0]["total"]) == 100_000
    assert float(data["total_expense"]) == 110_000 and data["merchants"] == 2
    assert data["items"][0]["pct"] == 90.9 and data["items"][1]["pct"] == 9.1


def test_notes_without_merchant_are_grouped_apart(client, auth, bank):
    add(client, auth, bank, 5_000, "")
    add(client, auth, bank, 7_000, "123")
    data = merchants(client, auth)
    assert data["items"][0]["name"] == "(sin nota)" and data["items"][0]["count"] == 2


def test_only_real_expenses_of_the_month_count(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={"name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    add(client, auth, bank, 1_000_000, "Nómina", kind="income")
    add(client, auth, bank, 40_000, "Uber")
    add(client, auth, bank, 99_000, "Uber", day=f"{prev_month(MONTH)}-10")           # mes pasado
    client.post("/api/transfers", headers=auth, json={"from_account_id": bank["id"], "to_account_id": other["id"], "amount": 77_000, "date": TODAY.isoformat()})
    client.post("/api/loans", headers=auth, json={"person": "Ana", "direction": "lent", "amount": 55_000, "date": TODAY.isoformat(), "account_id": bank["id"]})
    data = merchants(client, auth)
    assert [i["name"] for i in data["items"]] == ["Uber"] and float(data["total_expense"]) == 40_000
    assert merchants(client, auth, month=prev_month(MONTH))["items"][0]["name"] == "Uber"


def test_limit_ordering_validation_and_privacy(client, auth, bank):
    for i, name in enumerate(["Alfa", "Beta", "Gamma", "Delta"], start=1):
        add(client, auth, bank, i * 1_000, name)
    top2 = merchants(client, auth, limit=2)
    assert [i["name"] for i in top2["items"]] == ["Delta", "Gamma"] and top2["merchants"] == 4
    assert client.get("/api/insights/merchants", headers=auth, params={"limit": 0}).status_code == 422
    assert client.get("/api/insights/merchants", headers=auth, params={"month": "2026-13"}).status_code == 422
    assert client.get("/api/insights/merchants").status_code == 401
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    assert merchants(client, {"Authorization": f"Bearer {tok}"})["items"] == []
