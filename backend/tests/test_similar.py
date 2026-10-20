from datetime import timedelta

from app.clock import today as clock_today

TODAY = clock_today()


def day(n: int) -> str:
    return (TODAY + timedelta(days=n)).isoformat()


def add(client, auth, account, amount=4_500, kind="expense", offset=0, note="café"):
    r = client.post("/api/transactions", headers=auth, json={"account_id": account["id"], "kind": kind, "amount": amount,
                                                             "date": day(offset), "note": note})
    assert r.status_code == 201
    return r.json()


def similar(client, auth, account, amount=4_500, kind="expense", offset=0, **extra):
    r = client.get("/api/transactions/similar", headers=auth,
                   params={"account_id": account["id"], "amount": amount, "date": day(offset), "kind": kind, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_finds_the_same_amount_nearby(client, auth, bank):
    a = add(client, auth, bank, offset=0)
    found = similar(client, auth, bank)
    assert [f["id"] for f in found] == [a["id"]] and found[0]["note"] == "café" and float(found[0]["amount"]) == 4_500


def test_window_is_two_days_by_default_and_configurable(client, auth, bank):
    add(client, auth, bank, offset=-2)
    assert len(similar(client, auth, bank)) == 1                       # justo en el borde
    assert similar(client, auth, bank, offset=1) == []                 # a 3 días: no cuenta
    assert len(similar(client, auth, bank, offset=1, window=3)) == 1
    assert similar(client, auth, bank, offset=5, window=0) == []


def test_other_amount_kind_or_account_do_not_match(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={"name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    add(client, auth, bank, amount=4_500)
    assert similar(client, auth, bank, amount=4_501) == []
    assert similar(client, auth, bank, kind="income") == []
    assert similar(client, auth, other) == []


def test_transfers_and_loans_are_ignored(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={"name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    client.post("/api/transfers", headers=auth, json={"from_account_id": bank["id"], "to_account_id": other["id"], "amount": 4_500, "date": day(0)})
    client.post("/api/loans", headers=auth, json={"person": "Ana", "direction": "lent", "amount": 4_500, "date": day(0), "account_id": bank["id"]})
    assert similar(client, auth, bank) == []


def test_limit_of_five_and_newest_first(client, auth, bank):
    for offset in (-2, -1, 0, 1, 2, 0, 1):
        add(client, auth, bank, offset=offset)
    found = similar(client, auth, bank)
    assert len(found) == 5 and [f["date"] for f in found] == sorted((f["date"] for f in found), reverse=True)


def test_validation_and_privacy(client, auth, bank):
    base = {"account_id": bank["id"], "amount": 10, "date": day(0)}
    assert client.get("/api/transactions/similar", headers=auth, params={**base, "amount": 0}).status_code == 422
    assert client.get("/api/transactions/similar", headers=auth, params={**base, "window": 11}).status_code == 422
    assert client.get("/api/transactions/similar", headers=auth, params={**base, "kind": "otro"}).status_code == 422
    assert client.get("/api/transactions/similar", headers=auth, params={**base, "account_id": 999}).status_code == 404
    assert client.get("/api/transactions/similar", params=base).status_code == 401
    add(client, auth, bank, amount=10)
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    assert client.get("/api/transactions/similar", headers={"Authorization": f"Bearer {tok}"}, params=base).status_code == 404
