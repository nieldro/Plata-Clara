from datetime import datetime, timezone

from app import clock
from app.services.queries import budget_rows
from conftest import category_id


def freeze(monkeypatch, y, m, d, hour=17):  # 17:00 UTC = 12:00 en Bogotá: sin cambios de día por la zona horaria
    monkeypatch.setattr(clock, "_utcnow", lambda: datetime(y, m, d, hour, 0, tzinfo=timezone.utc))


def spend(client, auth, account, category, amount, day):
    r = client.post("/api/transactions", headers=auth, json={"account_id": account["id"], "category_id": category,
                                                             "kind": "expense", "amount": amount, "date": day})
    assert r.status_code == 201


def row(client, auth, month=None):
    params = {"month": month} if month else {}
    return client.get("/api/budgets", headers=auth, params=params).json()["items"][0]


def test_daily_allowance_and_projection_mid_month(client, auth, bank, monkeypatch):
    freeze(monkeypatch, 2026, 10, 10)
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 310_000})
    spend(client, auth, bank, mercado, 100_000, "2026-10-05")
    r = row(client, auth)
    # quedan 210.000 y faltan 22 días (del 10 al 31, contando hoy): 9.545,45 por día
    assert float(r["daily_allowance"]) == 9_545.45
    # 100.000 en 10 días → a ese ritmo, 310.000 en el mes (justo el tope: no se pasa)
    assert float(r["projected_spend"]) == 310_000 and r["projected_over"] is False


def test_projected_over_when_the_pace_is_too_fast(client, auth, bank, monkeypatch):
    freeze(monkeypatch, 2026, 10, 10)
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 310_000})
    spend(client, auth, bank, mercado, 120_000, "2026-10-04")
    r = row(client, auth)
    assert float(r["projected_spend"]) == 372_000 and r["projected_over"] is True


def test_exhausted_budget_leaves_nothing_per_day(client, auth, bank, monkeypatch):
    freeze(monkeypatch, 2026, 10, 15)
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 100_000})
    spend(client, auth, bank, mercado, 150_000, "2026-10-02")
    r = row(client, auth)
    assert float(r["daily_allowance"]) == 0 and r["projected_over"] is True and float(r["remaining"]) == -50_000


def test_first_and_last_day_of_the_month(client, auth, bank, monkeypatch):
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 310_000})
    freeze(monkeypatch, 2026, 10, 1)
    assert float(row(client, auth)["daily_allowance"]) == 10_000 and float(row(client, auth)["projected_spend"]) == 0   # 310.000 / 31
    spend(client, auth, bank, mercado, 10_000, "2026-10-31")
    freeze(monkeypatch, 2026, 10, 31)
    assert float(row(client, auth)["daily_allowance"]) == 300_000        # queda 1 día: todo lo que sobra


def test_february_and_leap_years_use_the_real_number_of_days(client, auth, bank, monkeypatch):
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 280_000})
    freeze(monkeypatch, 2027, 2, 1)
    assert float(row(client, auth)["daily_allowance"]) == 10_000         # 280.000 / 28
    freeze(monkeypatch, 2028, 2, 1)
    assert float(row(client, auth)["daily_allowance"]) == 9_655.17       # 280.000 / 29


def test_past_and_future_months_have_no_pace(client, auth, bank, monkeypatch):
    freeze(monkeypatch, 2026, 10, 10)
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 100_000})
    for month in ("2026-09", "2026-11"):
        r = row(client, auth, month)
        assert r["daily_allowance"] is None and r["projected_spend"] is None and r["projected_over"] is None


def test_budget_rows_accepts_an_explicit_today(client, auth, bank):
    from datetime import date
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 300_000})
    # sin pasar por la API: la función se puede probar con la fecha que se quiera
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    rows = budget_rows(db, 1, "2026-06", today=date(2026, 6, 15))
    assert float(rows[0]["daily_allowance"]) == 18_750                    # 300.000 / 16 días (del 15 al 30, contando hoy)
