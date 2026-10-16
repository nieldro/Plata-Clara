from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app import clock
from app.config import Settings, settings
from app.services.queries import current_month


def freeze(monkeypatch, y, m, d, hh, mm=0):
    monkeypatch.setattr(clock, "_utcnow", lambda: datetime(y, m, d, hh, mm, tzinfo=timezone.utc))


def test_evening_in_colombia_is_still_the_same_day(monkeypatch):
    freeze(monkeypatch, 2026, 10, 16, 3, 30)        # 03:30 UTC del 16 = 22:30 del 15 en Bogotá
    assert clock.today() == date(2026, 10, 15)
    freeze(monkeypatch, 2026, 10, 16, 5, 0)         # 00:00 en Bogotá: ya es el 16
    assert clock.today() == date(2026, 10, 16)


def test_month_does_not_roll_over_early_on_the_last_evening(monkeypatch):
    freeze(monkeypatch, 2026, 11, 1, 2, 0)          # 21:00 del 31 de octubre en Bogotá
    assert current_month() == "2026-10"
    freeze(monkeypatch, 2026, 11, 1, 5, 30)
    assert current_month() == "2026-11"


def test_timezone_is_configurable(monkeypatch):
    freeze(monkeypatch, 2026, 10, 16, 3, 30)
    monkeypatch.setattr(settings, "timezone", "UTC")
    assert clock.today() == date(2026, 10, 16)
    monkeypatch.setattr(settings, "timezone", "Asia/Tokyo")
    assert clock.today() == date(2026, 10, 16)
    monkeypatch.setattr(settings, "timezone", "America/Bogota")
    assert clock.today() == date(2026, 10, 15)


def test_invalid_timezone_is_rejected_at_startup():
    with pytest.raises(ValidationError, match="no existe"):
        Settings(timezone="Marte/Olympus")
    assert Settings(timezone="America/Bogota").timezone == "America/Bogota"


def test_recurring_does_not_run_a_day_early_at_night(client, auth, bank, monkeypatch):
    freeze(monkeypatch, 2026, 10, 16, 3, 30)  # 22:30 del 15 en Bogotá
    for day, note in (("2026-10-15", "vence hoy"), ("2026-10-16", "vence mañana")):
        client.post("/api/recurring", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": 1000,
                                                          "note": note, "start_date": day})
    assert client.post("/api/recurring/run", headers=auth).json()["created"] == 1
    assert [t["note"] for t in client.get("/api/transactions", headers=auth).json()] == ["vence hoy"]
    freeze(monkeypatch, 2026, 10, 16, 6, 0)  # ya es el 16 en Bogotá
    assert client.post("/api/recurring/run", headers=auth).json()["created"] == 1


def test_budget_month_uses_local_month(client, auth, bank, monkeypatch):
    freeze(monkeypatch, 2026, 11, 1, 2, 0)    # 31 de octubre, 21:00
    assert client.get("/api/budgets", headers=auth).json()["month"] == "2026-10"
