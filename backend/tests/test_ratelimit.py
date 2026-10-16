import pytest

from app.services import ratelimit
from app.services.ratelimit import SlidingWindowLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture()
def clock(monkeypatch):
    c = FakeClock()
    for limiter in (ratelimit.login_limiter, ratelimit.login_ip_limiter, ratelimit.register_limiter):
        monkeypatch.setattr(limiter, "clock", c)
    return c


def register(client, email="a@a.co"):
    return client.post("/api/auth/register", json={"email": email, "password": "12345678", "name": "A"})


def login(client, email="a@a.co", password="12345678"):
    return client.post("/api/auth/login", data={"username": email, "password": password})


# ---- el limitador en sí
def test_limiter_blocks_after_max_and_reports_wait():
    clock = FakeClock()
    lim = SlidingWindowLimiter(3, 60, clock)
    for _ in range(3):
        assert lim.retry_after("k") == 0
        lim.record("k")
    assert 1 <= lim.retry_after("k") <= 61
    clock.now += 61
    assert lim.retry_after("k") == 0  # la ventana venció


def test_limiter_window_slides_and_keys_are_independent():
    clock = FakeClock()
    lim = SlidingWindowLimiter(2, 100, clock)
    lim.record("a"); clock.now += 60; lim.record("a")
    assert lim.retry_after("a") > 0 and lim.retry_after("b") == 0
    clock.now += 50  # el primer evento ya salió de la ventana
    assert lim.retry_after("a") == 0


def test_limiter_memory_is_bounded(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_KEYS", 50)
    lim = SlidingWindowLimiter(5, 10_000, FakeClock())
    for i in range(500):
        lim.record(f"k{i}")
    assert len(lim._events) <= 50


# ---- el login
def test_lockout_after_five_failures_then_even_correct_password_is_refused(client, clock):
    register(client)
    for _ in range(5):
        assert login(client, password="mala").status_code == 401
    r = login(client, password="mala")
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0 and "minuto" in r.json()["detail"]
    assert login(client).status_code == 429  # la contraseña buena tampoco entra mientras dura el bloqueo

    clock.now += 15 * 60 + 5
    assert login(client).status_code == 200


def test_successful_login_resets_the_counter(client, clock):
    register(client)
    for _ in range(4):
        login(client, password="mala")
    assert login(client).status_code == 200
    for _ in range(4):  # el contador empezó de cero
        assert login(client, password="mala").status_code == 401


def test_unknown_email_is_locked_exactly_like_a_real_one(client, clock):
    register(client)
    codes = [login(client, "nadie@x.co", "x").status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]  # no revela qué correos existen


def test_lockout_is_per_email_and_email_case_is_ignored(client, clock):
    register(client)
    register(client, "b@b.co")
    for _ in range(5):
        login(client, "A@A.co", "mala")
    assert login(client, "a@a.co").status_code == 429
    assert login(client, "b@b.co").status_code == 200  # otra cuenta desde la misma IP sigue entrando


def test_ip_wide_limit_stops_password_spraying(client, clock, monkeypatch):
    monkeypatch.setattr(ratelimit.login_ip_limiter, "max_events", 8)
    register(client)
    for i in range(8):
        assert login(client, f"u{i}@x.co", "x").status_code == 401  # cada correo distinto: no salta el límite por correo
    assert login(client, "otro@x.co", "x").status_code == 429
    assert login(client).status_code == 429


def test_registration_limit_per_hour(client, clock):
    for i in range(10):
        assert register(client, f"u{i}@x.co").status_code == 201
    assert register(client, "u11@x.co").status_code == 429
    clock.now += 3601
    assert register(client, "u11@x.co").status_code == 201
