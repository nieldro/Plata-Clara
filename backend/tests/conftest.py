import os

# Antes de importar la app: que no toque dev.db ni una base real.
import tempfile

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="plata-clara-tests-")  # nunca escribe en la carpeta real
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-de-al-menos-32-caracteres")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db, make_sqlite_unicode_aware
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Cliente de la API sobre una base SQLite en memoria y una carpeta de archivos, nuevas en cada prueba."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    make_sqlite_unicode_aware(engine)

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_conn, _):  # como PostgreSQL: borrar algo referenciado debe fallar
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def auth(client):
    """Headers de un usuario ya registrado y con sesión."""
    client.post("/api/auth/register", json={"email": "t@t.co", "password": "12345678", "name": "Test"})
    token = client.post("/api/auth/login", data={"username": "t@t.co", "password": "12345678"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def bank(client, auth):
    """Una cuenta de ahorros con $1.000.000."""
    r = client.post("/api/accounts", headers=auth,
                    json={"name": "Ahorros", "type": "savings", "institution": "bancolombia", "initial_balance": 1_000_000})
    return r.json()


def category_id(client, auth, name):
    return next(c["id"] for c in client.get("/api/categories", headers=auth).json() if c["name"] == name)
