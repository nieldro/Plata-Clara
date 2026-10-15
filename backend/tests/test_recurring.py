from datetime import date

from app.services.recurring import add_months


def test_add_months_clamps_short_months():
    assert add_months(date(2026, 1, 31), 1, 31) == date(2026, 2, 28)
    assert add_months(date(2026, 2, 28), 1, 31) == date(2026, 3, 31)  # recupera el día 31
    assert add_months(date(2026, 12, 15), 1, 15) == date(2027, 1, 15)


def test_run_catches_up_and_is_idempotent(client, auth, bank):
    today = date.today()
    start = add_months(today.replace(day=1), -2, 1)  # hace 2 meses → 3 ocurrencias (incluye hoy si cae)
    r = client.post("/api/recurring", headers=auth, json={
        "account_id": bank["id"], "kind": "expense", "amount": 100_000,
        "note": "Arriendo", "frequency": "monthly", "start_date": start.isoformat(),
    })
    assert r.status_code == 201

    first = client.post("/api/recurring/run", headers=auth).json()
    assert first["created"] == 3
    assert client.post("/api/recurring/run", headers=auth).json()["created"] == 0

    acc = client.get("/api/accounts", headers=auth).json()[0]
    assert float(acc["balance"]) == 1_000_000 - 300_000
    nxt = client.get("/api/recurring", headers=auth).json()[0]["next_date"]
    assert nxt > today.isoformat()


def test_paused_recurring_does_not_run(client, auth, bank):
    start = add_months(date.today().replace(day=1), -1, 1)
    rec = client.post("/api/recurring", headers=auth, json={
        "account_id": bank["id"], "kind": "income", "amount": 50_000,
        "frequency": "weekly", "start_date": start.isoformat(),
    }).json()
    assert client.post(f"/api/recurring/{rec['id']}/toggle", headers=auth).json()["active"] is False
    assert client.post("/api/recurring/run", headers=auth).json()["created"] == 0


def test_recurring_on_credit_card_raises_debt(client, auth):
    card = client.post("/api/accounts", headers=auth, json={
        "name": "Visa", "type": "credit_card", "institution": "davivienda",
        "initial_balance": 0, "credit_limit": 2_000_000,
    }).json()
    client.post("/api/recurring", headers=auth, json={
        "account_id": card["id"], "kind": "expense", "amount": 40_000, "note": "Netflix",
        "frequency": "monthly", "start_date": date.today().isoformat(),
    })
    assert client.post("/api/recurring/run", headers=auth).json()["created"] == 1
    debts = client.get("/api/debts", headers=auth).json()
    assert float(debts[0]["current_balance"]) == 40_000


def test_recurring_rejects_foreign_account(client, auth):
    r = client.post("/api/recurring", headers=auth, json={
        "account_id": 999, "kind": "expense", "amount": 1, "start_date": date.today().isoformat(),
    })
    assert r.status_code == 404
