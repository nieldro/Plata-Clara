from app.db import get_db
from app.main import app


def test_liveness_does_not_need_the_database(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_readiness_checks_the_database(client):
    r = client.get("/health/ready")
    assert r.status_code == 200 and r.json() == {"status": "ok", "database": "ok"}


def test_readiness_returns_503_when_the_database_is_down(client):
    class BrokenSession:
        def execute(self, *_a, **_k):
            raise ConnectionError("la base no responde")

        def close(self):
            pass

    def broken():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken
    r = client.get("/health/ready")
    assert r.status_code == 503 and r.json()["detail"] == {"status": "error", "database": "down"}
    assert "la base no responde" not in r.text  # el error interno no se filtra al exterior
    assert client.get("/health").status_code == 200  # estar vivo no depende de la base
