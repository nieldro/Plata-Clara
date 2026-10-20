from datetime import timedelta

from app.clock import today as clock_today

TODAY = clock_today()


def iso(n: int) -> str:
    return (TODAY + timedelta(days=n)).isoformat()


def forecast(client, auth, days=60):
    r = client.get("/api/forecast", headers=auth, params={"days": days})
    assert r.status_code == 200
    return r.json()


def recurring(client, auth, account, amount, start, kind="expense", note="x", frequency="monthly"):
    client.post("/api/recurring", headers=auth, json={"account_id": account["id"], "kind": kind, "amount": amount,
                                                      "note": note, "frequency": frequency, "start_date": iso(start)})


def at(f, offset):
    return next(float(p["balance"]) for p in f["series"] if p["date"] == iso(offset))


def test_balance_changes_on_the_right_days(client, auth, bank):
    recurring(client, auth, bank, 300_000, 10, note="Arriendo")
    recurring(client, auth, bank, 100_000, 20, kind="income", note="Extra")
    f = forecast(client, auth, 30)
    assert float(f["start"]) == 1_000_000 and len(f["series"]) == 31
    assert at(f, 9) == 1_000_000 and at(f, 10) == 700_000 and at(f, 19) == 700_000 and at(f, 20) == 800_000
    assert float(f["end"]) == 800_000 and float(f["lowest"]["balance"]) == 700_000 and f["lowest"]["date"] == iso(10)
    assert f["will_run_short"] is False and f["first_negative_date"] is None


def test_warns_when_the_balance_goes_negative(client, auth, bank):
    recurring(client, auth, bank, 600_000, 5, note="Uno")
    recurring(client, auth, bank, 600_000, 12, note="Dos")
    f = forecast(client, auth, 30)
    assert f["will_run_short"] is True and f["first_negative_date"] == iso(12)
    assert at(f, 12) == -200_000 and float(f["lowest"]["balance"]) == -200_000


def test_credit_card_debt_is_not_counted_as_cash_but_its_payment_is_an_outflow(client, auth, bank):
    due = TODAY + timedelta(days=6)
    client.post("/api/accounts", headers=auth, json={"name": "Visa", "type": "credit_card", "institution": "bbva",
                                                     "initial_balance": 2_000_000, "due_day": due.day, "monthly_payment": 250_000})
    f = forecast(client, auth, 30)
    assert float(f["start"]) == 1_000_000          # la deuda de 2 millones no resta del efectivo de hoy
    assert at(f, 6) == 750_000                     # pero la cuota sí sale el día de pago


def test_unknown_amounts_and_overdue_loans_are_reported_not_counted(client, auth, bank):
    due = TODAY + timedelta(days=4)
    client.post("/api/accounts", headers=auth, json={"name": "Master", "type": "credit_card", "institution": "itau",
                                                     "initial_balance": 50_000, "due_day": due.day})   # sin pago habitual
    client.post("/api/loans", headers=auth, json={"person": "Ana", "direction": "lent", "amount": 500_000,
                                                  "date": iso(-30), "due_date": iso(-5)})
    f = forecast(client, auth, 30)
    assert f["unknown_amounts"] == 1 and f["overdue_excluded"] == 1
    assert float(f["end"]) == 1_000_000            # ni el pago sin monto ni el cobro vencido cambian el saldo


def test_future_loan_collection_is_counted(client, auth, bank):
    client.post("/api/loans", headers=auth, json={"person": "Luis", "direction": "lent", "amount": 80_000,
                                                  "date": iso(0), "due_date": iso(7)})
    assert at(forecast(client, auth, 30), 7) == 1_080_000


def test_empty_user_and_validation_and_privacy(client, auth):
    f = forecast(client, auth, 7)
    assert float(f["start"]) == 0 and f["will_run_short"] is False and len(f["series"]) == 8
    assert client.get("/api/forecast", headers=auth, params={"days": 6}).status_code == 422
    assert client.get("/api/forecast", headers=auth, params={"days": 181}).status_code == 422
    assert client.get("/api/forecast").status_code == 401


def test_each_user_only_sees_their_own_cash(client, auth, bank):
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    assert float(forecast(client, other, 7)["start"]) == 0
    assert float(forecast(client, auth, 7)["start"]) == 1_000_000
