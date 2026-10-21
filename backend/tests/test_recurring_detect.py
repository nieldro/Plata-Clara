from datetime import timedelta

from app.clock import today as clock_today
from conftest import category_id

TODAY = clock_today()


def day(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def add(client, auth, account, amount, note, offset, kind="expense", category=None):
    r = client.post("/api/transactions", headers=auth, json={"account_id": account["id"], "kind": kind, "amount": amount,
                                                             "note": note, "date": day(offset), "category_id": category})
    assert r.status_code == 201


def series(client, auth, account, amount, note, offsets, **kw):
    for o in offsets:
        add(client, auth, account, amount, note, o, **kw)


def found(client, auth):
    r = client.get("/api/recurring/suggestions", headers=auth)
    assert r.status_code == 200
    return r.json()


def test_monthly_subscription_is_detected_with_next_date_in_the_future(client, auth, bank):
    ocio = category_id(client, auth, "Ocio")
    series(client, auth, bank, 39_900, "Netflix", [-92, -62, -32], category=ocio)
    [s] = found(client, auth)
    assert s["note"] == "Netflix" and s["frequency"] == "monthly" and s["occurrences"] == 3
    assert float(s["amount"]) == 39_900 and s["kind"] == "expense" and s["category_id"] == ocio and s["account_id"] == bank["id"]
    assert s["last_date"] == day(-32) and s["start_date"] >= day(0)       # jamás en el pasado: no duplicaría lo ya registrado


def test_weekly_and_biweekly_patterns(client, auth, bank):
    series(client, auth, bank, 15_000, "Clase de yoga", [-21, -14, -7])
    series(client, auth, bank, 200_000, "Quincena aseo", [-60, -45, -30, -15], kind="expense")
    got = {s["note"]: s["frequency"] for s in found(client, auth)}
    assert got == {"Clase de yoga": "weekly", "Quincena aseo": "biweekly"}


def test_income_is_detected_too(client, auth, bank):
    series(client, auth, bank, 3_000_000, "Nómina empresa", [-95, -65, -35], kind="income")
    assert [(s["kind"], s["frequency"]) for s in found(client, auth)] == [("income", "monthly")]


def test_small_amount_variations_are_tolerated_but_big_ones_are_not(client, auth, bank):
    for offset, amount in ((-92, 100_000), (-62, 102_000), (-32, 98_000)):
        add(client, auth, bank, amount, "Gimnasio", offset)
    for offset, amount in ((-92, 50_000), (-62, 90_000), (-32, 20_000)):
        add(client, auth, bank, amount, "Mercado", offset)
    assert [s["note"] for s in found(client, auth)] == ["Gimnasio"]


def test_not_enough_repetitions_or_irregular_gaps_are_ignored(client, auth, bank):
    series(client, auth, bank, 10_000, "Dos veces", [-62, -32])
    series(client, auth, bank, 10_000, "Irregular", [-100, -90, -20])
    series(client, auth, bank, 10_000, "Todos los dias", [-3, -2, -1])
    assert found(client, auth) == []


def test_cancelled_subscriptions_are_not_suggested(client, auth, bank):
    series(client, auth, bank, 39_900, "Netflix", [-300, -270, -240])     # dejó de repetirse hace meses
    assert found(client, auth) == []


def test_already_recurring_is_not_suggested_again(client, auth, bank):
    series(client, auth, bank, 39_900, "Netflix", [-92, -62, -32])
    client.post("/api/recurring", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": 39_900,
                                                      "note": "netflix mensual", "frequency": "monthly", "start_date": day(5)})
    assert found(client, auth) == []
    rec = client.get("/api/recurring", headers=auth).json()[0]
    client.post(f"/api/recurring/{rec['id']}/toggle", headers=auth)         # pausado: otra vez es candidato
    assert len(found(client, auth)) == 1


def test_different_accounts_are_separate_patterns(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={"name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    series(client, auth, bank, 20_000, "Spotify", [-92, -62, -32])
    series(client, auth, other, 20_000, "Spotify", [-92, -62])               # solo 2 en la otra cuenta: no alcanza
    assert [s["account_id"] for s in found(client, auth)] == [bank["id"]]


def test_transfers_loans_and_notes_without_a_merchant_are_ignored(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={"name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    for o in (-92, -62, -32):
        client.post("/api/transfers", headers=auth, json={"from_account_id": bank["id"], "to_account_id": other["id"], "amount": 500, "date": day(o)})
    series(client, auth, bank, 7_000, "", [-92, -62, -32])
    series(client, auth, bank, 7_000, "123", [-92, -62, -32])
    assert found(client, auth) == []


def test_accepting_the_suggestion_does_not_backfill_old_movements(client, auth, bank):
    series(client, auth, bank, 39_900, "Netflix", [-92, -62, -32])
    [s] = found(client, auth)
    r = client.post("/api/recurring", headers=auth, json={"account_id": s["account_id"], "kind": s["kind"], "amount": s["amount"],
                                                          "note": s["note"], "frequency": s["frequency"], "start_date": s["start_date"]})
    assert r.status_code == 201
    created = client.post("/api/recurring/run", headers=auth).json()["created"]
    assert created <= 1 and len(client.get("/api/transactions", headers=auth).json()) in (3, 4)   # a lo sumo el de hoy
    assert found(client, auth) == []


def test_ordering_auth_and_privacy(client, auth, bank):
    series(client, auth, bank, 10_000, "Barato", [-92, -62, -32])
    series(client, auth, bank, 900_000, "Arriendo", [-92, -62, -32])
    assert [s["note"] for s in found(client, auth)] == ["Arriendo", "Barato"]
    assert client.get("/api/recurring/suggestions").status_code == 401
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    assert client.get("/api/recurring/suggestions", headers={"Authorization": f"Bearer {tok}"}).json() == []
