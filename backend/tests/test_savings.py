from datetime import date, timedelta


def goal(client, auth, **extra):
    body = {"name": "Viaje", "target_amount": 1_200_000,
            "target_date": (date.today() + timedelta(days=365)).isoformat(), **extra}
    r = client.post("/api/savings", headers=auth, json=body)
    assert r.status_code == 201
    return r.json()


def test_initial_amount_becomes_first_contribution(client, auth):
    g = goal(client, auth, current_amount=200_000)
    hist = client.get(f"/api/savings/{g['id']}/contributions", headers=auth).json()
    assert len(hist) == 1 and float(hist[0]["amount"]) == 200_000 and hist[0]["note"] == "Saldo inicial"


def test_deposit_withdraw_and_limits(client, auth):
    g = goal(client, auth)
    url = f"/api/savings/{g['id']}/contributions"
    assert float(client.post(url, headers=auth, json={"amount": 300_000}).json()["current_amount"]) == 300_000
    assert float(client.post(url, headers=auth, json={"amount": 100_000, "kind": "withdraw"}).json()["current_amount"]) == 200_000
    over = client.post(url, headers=auth, json={"amount": 999_999, "kind": "withdraw"})
    assert over.status_code == 422
    assert [float(c["amount"]) for c in client.get(url, headers=auth).json()] == [-100_000, 300_000]


def test_delete_contribution_reverts_goal(client, auth):
    g = goal(client, auth)
    url = f"/api/savings/{g['id']}/contributions"
    client.post(url, headers=auth, json={"amount": 400_000, "note": "Prima"})
    cid = client.get(url, headers=auth).json()[0]["id"]
    after = client.delete(f"{url}/{cid}", headers=auth).json()
    assert float(after["current_amount"]) == 0
    assert client.delete(f"{url}/{cid}", headers=auth).status_code == 404


def test_update_goal_partially(client, auth):
    g = goal(client, auth)
    r = client.patch(f"/api/savings/{g['id']}", headers=auth, json={"name": "Europa", "annual_rate": 8})
    assert r.json()["name"] == "Europa" and float(r.json()["annual_rate"]) == 8
    assert float(r.json()["target_amount"]) == 1_200_000  # lo no enviado no cambia


def test_plan_projection_reaches_target(client, auth):
    g = goal(client, auth, current_amount=100_000, annual_rate=10)
    p = client.get(f"/api/savings/{g['id']}/plan", headers=auth).json()
    proj = p["projection"]
    assert len(proj) == p["months_left"] + 1
    assert proj[0]["balance"] == 100_000
    # con el aporte mensual calculado, el último punto de la proyección es la meta
    assert abs(proj[-1]["balance"] - 1_200_000) < 1
    assert p["monthly_contribution"] > 0


def test_cannot_touch_other_users_goal(client, auth):
    g = goal(client, auth)
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    assert client.get(f"/api/savings/{g['id']}/plan", headers=other).status_code == 404
    assert client.patch(f"/api/savings/{g['id']}", headers=other, json={"name": "x"}).status_code == 404
