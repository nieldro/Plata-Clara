import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def exploding_route():
    @app.get("/_test/boom")
    def boom():
        raise RuntimeError("secreto interno: clave=abc123")

    yield
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != "/_test/boom"]


def test_unexpected_error_returns_generic_json(client, exploding_route):
    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/_test/boom")
    assert r.status_code == 500
    assert r.headers["content-type"].startswith("application/json")
    assert "inesperado" in r.json()["detail"]
    assert "abc123" not in r.text  # el detalle interno no sale hacia el cliente
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_unexpected_error_is_logged_with_its_traceback(client, exploding_route, caplog):
    c = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        c.get("/_test/boom")
    record = next(r for r in caplog.records if "GET /_test/boom" in r.getMessage())
    assert record.exc_info and "secreto interno" in str(record.exc_info[1])
