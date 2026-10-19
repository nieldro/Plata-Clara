import pytest

from app.services import ratelimit

CSV = "Fecha;Descripción;Valor\n05/03/2026;Café;-4.000\n".encode("cp1252")


class Clock:
    now = 5000.0

    def __call__(self):
        return self.now


@pytest.fixture()
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(ratelimit.heavy_limiter, "clock", c)
    monkeypatch.setattr(ratelimit.heavy_limiter, "max_events", 3)
    return c


def export(client, headers):
    return client.get("/api/export/transactions", headers=headers, params={"format": "csv"})


def test_exports_are_limited_per_minute(client, auth, clock):
    assert [export(client, auth).status_code for _ in range(3)] == [200, 200, 200]
    r = export(client, auth)
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0 and "demasiados archivos" in r.json()["detail"]
    clock.now += 61
    assert export(client, auth).status_code == 200


def test_reports_and_exports_share_the_same_budget(client, auth, clock):
    export(client, auth)
    client.get("/api/reports/monthly", headers=auth)
    export(client, auth)
    assert client.get("/api/reports/monthly", headers=auth).status_code == 429


def test_statement_preview_is_limited_too(client, auth, bank, clock):
    def preview():
        return client.post("/api/imports/preview", headers=auth, files={"file": ("e.csv", CSV, "text/csv")},
                           data={"account_id": str(bank["id"])})
    assert [preview().status_code for _ in range(3)] == [200, 200, 200]
    assert preview().status_code == 429


def test_limit_is_per_user_and_does_not_touch_normal_endpoints(client, auth, clock):
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    for _ in range(4):
        export(client, auth)
    assert export(client, auth).status_code == 429          # el primer usuario está bloqueado
    assert export(client, other).status_code == 200         # el segundo no
    assert client.get("/api/accounts", headers=auth).status_code == 200  # lo normal sigue funcionando
    assert client.get("/api/transactions", headers=auth).status_code == 200


def test_unauthenticated_requests_do_not_consume_the_budget(client, auth, clock):
    for _ in range(10):
        assert client.get("/api/export/transactions").status_code == 401
    assert export(client, auth).status_code == 200
