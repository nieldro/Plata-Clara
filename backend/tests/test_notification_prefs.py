from datetime import timedelta

from app.clock import today as clock_today
from conftest import category_id

TODAY = clock_today()


def prefs(client, auth):
    return {k["kind"]: k["enabled"] for k in client.get("/api/notifications/preferences", headers=auth).json()["kinds"]}


def mute(client, auth, *kinds):
    return client.put("/api/notifications/preferences", headers=auth, json={"muted": list(kinds)})


def refresh(client, auth):
    return client.post("/api/notifications/refresh", headers=auth).json()


def over_budget(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 100_000})
    client.post("/api/transactions", headers=auth, json={"account_id": bank["id"], "category_id": mercado, "kind": "expense",
                                                         "amount": 150_000, "date": TODAY.isoformat()})


def test_everything_is_enabled_by_default_and_lists_all_kinds(client, auth):
    kinds = client.get("/api/notifications/preferences", headers=auth).json()["kinds"]
    assert [k["kind"] for k in kinds] == ["budget", "due", "goal", "loan", "recurring"]
    assert all(k["enabled"] and k["label"] for k in kinds)


def test_muting_budget_alerts_stops_new_ones(client, auth, bank):
    first = mute(client, auth, "budget").json()["kinds"][0]
    assert first["kind"] == "budget" and first["enabled"] is False
    over_budget(client, auth, bank)
    r = refresh(client, auth)
    assert r["new"] == 0 and r["items"] == [] and r["unread"] == 0
    assert prefs(client, auth) == {"budget": False, "due": True, "goal": True, "loan": True, "recurring": True}


def test_unmuting_lets_the_alert_in_later(client, auth, bank):
    mute(client, auth, "budget")
    over_budget(client, auth, bank)
    assert refresh(client, auth)["new"] == 0
    mute(client, auth)                                           # vuelve a activarlo todo
    r = refresh(client, auth)
    assert r["new"] == 1 and "Superaste" in r["items"][0]["title"]


def test_already_received_alerts_are_hidden_while_muted_and_return_after(client, auth, bank):
    over_budget(client, auth, bank)
    assert refresh(client, auth)["unread"] == 1
    mute(client, auth, "budget")
    hidden = client.get("/api/notifications", headers=auth).json()
    assert hidden["items"] == [] and hidden["unread"] == 0       # ni se ve ni cuenta como no leído
    mute(client, auth)
    assert client.get("/api/notifications", headers=auth).json()["unread"] == 1


def test_other_kinds_keep_working_when_one_is_muted(client, auth, bank):
    mute(client, auth, "budget")
    over_budget(client, auth, bank)
    client.post("/api/savings", headers=auth, json={"name": "Viaje", "target_amount": 1_000, "current_amount": 1_000,
                                                    "target_date": (TODAY + timedelta(days=200)).isoformat()})
    r = refresh(client, auth)
    assert [i["kind"] for i in r["items"]] == ["goal"]


def test_muting_recurring_and_loan_alerts(client, auth, bank):
    mute(client, auth, "recurring", "loan")
    client.post("/api/recurring", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": 10,
                                                      "note": "Spotify", "start_date": TODAY.isoformat()})
    assert client.post("/api/recurring/run", headers=auth).json()["created"] == 1       # sí se registra el movimiento…
    client.post("/api/loans", headers=auth, json={"person": "Ana", "direction": "lent", "amount": 5, "date": TODAY.isoformat(),
                                                  "due_date": (TODAY + timedelta(days=1)).isoformat()})
    r = refresh(client, auth)
    assert r["items"] == [] and r["new"] == 0                                           # …pero sin aviso


def test_preferences_replace_the_whole_set_and_ignore_repeats(client, auth):
    mute(client, auth, "budget", "due")
    mute(client, auth, "goal", "goal")
    assert prefs(client, auth) == {"budget": True, "due": True, "goal": False, "loan": True, "recurring": True}


def test_validation_and_privacy(client, auth):
    assert mute(client, auth, "inventado").status_code == 422
    assert client.put("/api/notifications/preferences", headers=auth, json={}).status_code == 422
    assert client.put("/api/notifications/preferences", json={"muted": []}).status_code == 401
    assert client.get("/api/notifications/preferences").status_code == 401
    mute(client, auth, "budget")
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    assert all(prefs(client, {"Authorization": f"Bearer {tok}"}).values())              # la otra persona no heredó nada
