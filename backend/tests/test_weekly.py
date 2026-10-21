from datetime import date, datetime, timezone

from app import clock
from app.services.weekly import week_start
from conftest import category_id


def freeze(monkeypatch, y, m, d):  # 17:00 UTC = 12:00 en Bogotá: sin cambios de día por la zona horaria
    monkeypatch.setattr(clock, "_utcnow", lambda: datetime(y, m, d, 17, 0, tzinfo=timezone.utc))


def add(client, auth, account, amount, day, kind="expense", category=None, note=""):
    r = client.post("/api/transactions", headers=auth, json={"account_id": account["id"], "kind": kind, "amount": amount,
                                                             "date": day, "category_id": category, "note": note})
    assert r.status_code == 201


def weekly(client, auth):
    r = client.get("/api/insights/weekly", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def test_week_starts_on_monday():
    assert week_start(date(2026, 10, 21)) == date(2026, 10, 19)     # miércoles → lunes
    assert week_start(date(2026, 10, 19)) == date(2026, 10, 19)     # el propio lunes
    assert week_start(date(2026, 10, 25)) == date(2026, 10, 19)     # domingo


def test_this_week_vs_same_days_of_last_week(client, auth, bank, monkeypatch):
    freeze(monkeypatch, 2026, 10, 21)                               # miércoles: van 3 días (lun, mar, mié)
    mercado, ocio = category_id(client, auth, "Mercado"), category_id(client, auth, "Ocio")
    add(client, auth, bank, 100_000, "2026-10-19", category=mercado, note="Éxito")
    add(client, auth, bank, 60_000, "2026-10-21", category=ocio, note="Cine")
    add(client, auth, bank, 500_000, "2026-10-20", "income")
    add(client, auth, bank, 90_000, "2026-10-12", category=mercado)    # semana pasada, lunes: cuenta
    add(client, auth, bank, 60_000, "2026-10-14", category=mercado)    # semana pasada, miércoles: cuenta
    add(client, auth, bank, 700_000, "2026-10-16")                     # semana pasada, viernes: NO (aún no llegamos a ese día)
    w = weekly(client, auth)
    assert (w["week_start"], w["week_end"], w["days_elapsed"]) == ("2026-10-19", "2026-10-25", 3)
    assert float(w["expense"]) == 160_000 and float(w["income"]) == 500_000 and float(w["net"]) == 340_000 and w["transactions"] == 3
    assert float(w["previous_expense"]) == 150_000 and w["expense_change_pct"] == 6.7
    assert float(w["daily_average"]) == 53_333.33


def test_daily_series_marks_future_days_and_top_categories_and_biggest(client, auth, bank, monkeypatch):
    freeze(monkeypatch, 2026, 10, 21)
    mercado, ocio = category_id(client, auth, "Mercado"), category_id(client, auth, "Ocio")
    add(client, auth, bank, 100_000, "2026-10-19", category=mercado, note="Éxito")
    add(client, auth, bank, 40_000, "2026-10-19", category=mercado)
    add(client, auth, bank, 60_000, "2026-10-21", category=ocio, note="Cine")
    add(client, auth, bank, 5_000, "2026-10-21")
    w = weekly(client, auth)
    assert [(d["date"][-2:], float(d["expense"]), d["future"]) for d in w["daily"]] == [
        ("19", 140_000.0, False), ("20", 0.0, False), ("21", 65_000.0, False),
        ("22", 0.0, True), ("23", 0.0, True), ("24", 0.0, True), ("25", 0.0, True)]
    assert [(c["category"], float(c["total"])) for c in w["top_categories"]] == [
        ("Mercado", 140_000.0), ("Ocio", 60_000.0), ("Sin categoría", 5_000.0)]
    assert w["biggest_expense"]["note"] == "Éxito" and float(w["biggest_expense"]["amount"]) == 100_000
    assert w["biggest_expense"]["category"] == "Mercado" and w["biggest_expense"]["date"] == "2026-10-19"


def test_no_previous_data_means_no_percentage(client, auth, bank, monkeypatch):
    freeze(monkeypatch, 2026, 10, 21)
    add(client, auth, bank, 10_000, "2026-10-20")
    w = weekly(client, auth)
    assert w["expense_change_pct"] is None and float(w["previous_expense"]) == 0


def test_monday_and_empty_week(client, auth, bank, monkeypatch):
    freeze(monkeypatch, 2026, 10, 19)                                 # lunes: solo cuenta hoy
    w = weekly(client, auth)
    assert w["days_elapsed"] == 1 and w["transactions"] == 0 and w["biggest_expense"] is None
    assert float(w["expense"]) == 0 and float(w["daily_average"]) == 0 and w["top_categories"] == []
    assert sum(d["future"] for d in w["daily"]) == 6


def test_sunday_is_a_full_week(client, auth, bank, monkeypatch):
    freeze(monkeypatch, 2026, 10, 25)
    add(client, auth, bank, 70_000, "2026-10-25")
    add(client, auth, bank, 70_000, "2026-10-18")                     # domingo de la semana pasada: cuenta en la comparación
    w = weekly(client, auth)
    assert w["days_elapsed"] == 7 and not any(d["future"] for d in w["daily"])
    assert float(w["expense"]) == 70_000 and float(w["previous_expense"]) == 70_000 and w["expense_change_pct"] == 0.0


def test_transfers_and_loans_do_not_count_and_privacy(client, auth, bank, monkeypatch):
    freeze(monkeypatch, 2026, 10, 21)
    other = client.post("/api/accounts", headers=auth, json={"name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    client.post("/api/transfers", headers=auth, json={"from_account_id": bank["id"], "to_account_id": other["id"], "amount": 777, "date": "2026-10-20"})
    client.post("/api/loans", headers=auth, json={"person": "Ana", "direction": "lent", "amount": 555, "date": "2026-10-20", "account_id": bank["id"]})
    assert weekly(client, auth)["transactions"] == 0
    add(client, auth, bank, 10_000, "2026-10-20")
    assert client.get("/api/insights/weekly").status_code == 401
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    assert float(weekly(client, {"Authorization": f"Bearer {tok}"})["expense"]) == 0
