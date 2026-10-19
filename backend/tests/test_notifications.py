from datetime import timedelta
from app.clock import today as clock_today

from conftest import category_id


def refresh(client, auth):
    return client.post("/api/notifications/refresh", headers=auth).json()


def spend(client, auth, account, category, amount):
    client.post("/api/transactions", headers=auth, json={
        "account_id": account["id"], "category_id": category, "kind": "expense",
        "amount": amount, "date": clock_today().isoformat(),
    })


def test_budget_alerts_80_then_100_without_repeating(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 100_000})

    spend(client, auth, bank, mercado, 50_000)
    assert refresh(client, auth)["new"] == 0

    spend(client, auth, bank, mercado, 35_000)  # 85 %
    r = refresh(client, auth)
    assert r["new"] == 1 and "85%" in r["items"][0]["title"]
    assert refresh(client, auth)["new"] == 0  # no se repite

    spend(client, auth, bank, mercado, 30_000)  # 115 %
    r = refresh(client, auth)
    assert r["new"] == 1 and "Superaste" in r["items"][0]["title"]
    assert r["unread"] == 2


def test_card_due_date_alert(client, auth):
    soon = clock_today() + timedelta(days=2)
    client.post("/api/accounts", headers=auth, json={
        "name": "Visa", "type": "credit_card", "institution": "davivienda",
        "initial_balance": 500_000, "credit_limit": 3_000_000, "due_day": soon.day,
    })
    r = refresh(client, auth)
    assert r["new"] == 1
    assert r["items"][0]["kind"] == "due" and "Visa" in r["items"][0]["title"]


def test_no_due_alert_when_far_or_paid_off(client, auth):
    far = clock_today() + timedelta(days=15)
    client.post("/api/accounts", headers=auth, json={
        "name": "Lejos", "type": "credit_card", "institution": "bbva", "initial_balance": 500_000, "due_day": far.day,
    })
    soon = clock_today() + timedelta(days=1)
    client.post("/api/accounts", headers=auth, json={
        "name": "Saldada", "type": "credit_card", "institution": "bbva", "initial_balance": 0, "due_day": soon.day,
    })
    assert refresh(client, auth)["new"] == 0


def test_goal_close_to_deadline(client, auth):
    client.post("/api/savings", headers=auth, json={
        "name": "Viaje", "target_amount": 1_000_000, "target_date": (clock_today() + timedelta(days=10)).isoformat(),
    })
    r = refresh(client, auth)
    assert r["new"] == 1 and r["items"][0]["kind"] == "goal"


def test_goal_reached_is_celebrated_once(client, auth):
    far = (clock_today() + timedelta(days=200)).isoformat()
    g = client.post("/api/savings", headers=auth, json={"name": "Viaje", "target_amount": 1_000_000, "target_date": far}).json()
    assert refresh(client, auth)["new"] == 0                      # aún lejos y sin lograr: nada que avisar

    client.post(f"/api/savings/{g['id']}/contributions", headers=auth, json={"amount": 1_000_000})
    r = refresh(client, auth)
    assert r["new"] == 1 and "Lograste" in r["items"][0]["title"] and "Viaje" in r["items"][0]["title"]
    assert refresh(client, auth)["new"] == 0                      # no se repite

    client.post(f"/api/savings/{g['id']}/contributions", headers=auth, json={"amount": 5_000})  # pasarse tampoco repite
    assert refresh(client, auth)["new"] == 0


def test_goal_with_withdrawal_below_target_is_not_celebrated(client, auth):
    far = (clock_today() + timedelta(days=200)).isoformat()
    g = client.post("/api/savings", headers=auth, json={"name": "Auto", "target_amount": 500_000, "target_date": far,
                                                         "current_amount": 400_000}).json()
    client.post(f"/api/savings/{g['id']}/contributions", headers=auth, json={"amount": 50_000, "kind": "withdraw"})
    assert refresh(client, auth)["new"] == 0


def test_recurring_run_notifies_and_read_flow(client, auth, bank):
    client.post("/api/recurring", headers=auth, json={
        "account_id": bank["id"], "kind": "expense", "amount": 10_000, "note": "Spotify",
        "start_date": clock_today().isoformat(),
    })
    client.post("/api/recurring/run", headers=auth)
    data = client.get("/api/notifications", headers=auth).json()
    assert data["unread"] == 1 and "Spotify" in data["items"][0]["title"]

    nid = data["items"][0]["id"]
    assert client.post(f"/api/notifications/{nid}/read", headers=auth).status_code == 204
    assert client.get("/api/notifications", headers=auth).json()["unread"] == 0

    assert client.delete(f"/api/notifications/{nid}", headers=auth).status_code == 204
    assert client.get("/api/notifications", headers=auth).json()["items"] == []


def test_read_all(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 10_000})
    spend(client, auth, bank, mercado, 20_000)
    assert refresh(client, auth)["unread"] >= 1
    client.post("/api/notifications/read-all", headers=auth)
    assert client.get("/api/notifications", headers=auth).json()["unread"] == 0
