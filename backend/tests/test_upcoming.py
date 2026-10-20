from datetime import date, timedelta

from app.clock import today as clock_today

TODAY = clock_today()


def iso(d: date) -> str:
    return d.isoformat()


def get(client, auth, days=30):
    r = client.get("/api/upcoming", headers=auth, params={"days": days})
    assert r.status_code == 200
    return r.json()


def test_recurring_occurrences_inside_the_window(client, auth, bank):
    client.post("/api/recurring", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": 1_300_000,
                                                      "note": "Arriendo", "frequency": "monthly",
                                                      "start_date": iso(TODAY + timedelta(days=5))})
    client.post("/api/recurring", headers=auth, json={"account_id": bank["id"], "kind": "income", "amount": 100,
                                                      "note": "Semanal", "frequency": "weekly",
                                                      "start_date": iso(TODAY + timedelta(days=1))})
    data = get(client, auth, 30)
    rent = [i for i in data["items"] if i["title"] == "Arriendo"]
    weekly = [i for i in data["items"] if i["title"] == "Semanal"]
    assert len(rent) == 1 and rent[0]["days"] == 5 and float(rent[0]["amount"]) == 1_300_000
    assert len(weekly) == 5  # días 1, 8, 15, 22 y 29
    dates = [i["date"] for i in data["items"]]
    assert dates == sorted(dates)
    assert float(data["to_pay"]) == 1_300_000 and float(data["to_receive"]) == 500


def test_does_not_modify_recurring_and_ignores_paused(client, auth, bank):
    rec = client.post("/api/recurring", headers=auth, json={
        "account_id": bank["id"], "kind": "expense", "amount": 10, "note": "Pausado",
        "start_date": iso(TODAY + timedelta(days=2))}).json()
    get(client, auth)
    assert client.get("/api/recurring", headers=auth).json()[0]["next_date"] == rec["next_date"]  # sigue igual
    client.post(f"/api/recurring/{rec['id']}/toggle", headers=auth)
    assert get(client, auth)["items"] == []


def test_card_due_dates_with_and_without_a_usual_payment(client, auth):
    soon = TODAY + timedelta(days=4)
    client.post("/api/accounts", headers=auth, json={"name": "Visa", "type": "credit_card", "institution": "bbva",
                                                     "initial_balance": 800_000, "due_day": soon.day, "monthly_payment": 200_000})
    client.post("/api/accounts", headers=auth, json={"name": "Master", "type": "credit_card", "institution": "itau",
                                                     "initial_balance": 50_000, "due_day": soon.day})
    client.post("/api/accounts", headers=auth, json={"name": "Saldada", "type": "credit_card", "institution": "bbva",
                                                     "initial_balance": 0, "due_day": soon.day})
    items = [i for i in get(client, auth)["items"] if i["source"] == "debt"]
    by_title = {i["title"]: i for i in items if i["days"] == 4}
    assert float(by_title["Pago de BBVA Colombia · Visa"]["amount"]) == 200_000
    assert by_title["Pago de Itaú · Master"]["amount"] is None      # sin pago habitual: se sabe la fecha, no el monto
    assert not any("Saldada" in i["title"] for i in items)           # sin deuda no hay nada que pagar


def test_monthly_card_payment_repeats_in_a_long_window(client, auth):
    soon = TODAY + timedelta(days=3)
    client.post("/api/accounts", headers=auth, json={"name": "Visa", "type": "credit_card", "institution": "bbva",
                                                     "initial_balance": 100, "due_day": soon.day, "monthly_payment": 10})
    assert len([i for i in get(client, auth, 90)["items"] if i["source"] == "debt"]) >= 3


def test_loans_open_overdue_and_settled(client, auth):
    late = iso(TODAY - timedelta(days=3))
    old = iso(TODAY - timedelta(days=20))
    client.post("/api/loans", headers=auth, json={"person": "Ana", "direction": "lent", "amount": 90_000, "date": old, "due_date": late})
    client.post("/api/loans", headers=auth, json={"person": "Beto", "direction": "borrowed", "amount": 40_000, "date": iso(TODAY),
                                                  "due_date": iso(TODAY + timedelta(days=10))})
    paid = client.post("/api/loans", headers=auth, json={"person": "Pagado", "direction": "lent", "amount": 5, "date": old,
                                                         "due_date": late}).json()
    client.post(f"/api/loans/{paid['id']}/payments", headers=auth, json={"amount": 5, "date": iso(TODAY)})
    client.post("/api/loans", headers=auth, json={"person": "Lejos", "direction": "lent", "amount": 1, "date": iso(TODAY),
                                                  "due_date": iso(TODAY + timedelta(days=100))})
    items = get(client, auth)["items"]
    assert [i["title"] for i in items] == ["Ana te debe", "Le debes a Beto"]   # vencido primero; saldado y lejano fuera
    assert items[0]["overdue"] is True and items[0]["kind"] == "income" and items[1]["kind"] == "expense"


def test_window_validation_empty_state_and_privacy(client, auth, bank):
    assert get(client, auth) == {"days": 30, "to_pay": 0, "to_receive": 0, "items": []}
    assert client.get("/api/upcoming", headers=auth, params={"days": 0}).status_code == 422
    assert client.get("/api/upcoming", headers=auth, params={"days": 181}).status_code == 422
    assert client.get("/api/upcoming").status_code == 401
    client.post("/api/recurring", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": 1,
                                                      "start_date": iso(TODAY + timedelta(days=1))})
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    assert get(client, {"Authorization": f"Bearer {tok}"})["items"] == []
