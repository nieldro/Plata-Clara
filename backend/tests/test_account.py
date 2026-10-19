import json
import time
from datetime import datetime, timedelta, timezone
from app.clock import today as clock_today
from pathlib import Path

import jwt
from sqlalchemy import func, select

from app.config import settings

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
TODAY = clock_today().isoformat()


def hdr(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, email="t@t.co", password="12345678"):
    return client.post("/api/auth/login", data={"username": email, "password": password})


# ---------------------------------------------------------------- cambiar contraseña
def test_change_password_logs_in_with_new_and_rejects_old(client, auth):
    r = client.post("/api/account/password", headers=auth, json={"current_password": "12345678", "new_password": "nueva-clave-99"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=hdr(r.json()["access_token"])).status_code == 200  # la sesión nueva sirve
    assert login(client).status_code == 401
    assert login(client, password="nueva-clave-99").status_code == 200


def test_old_sessions_stop_working_after_password_change(client, auth):
    user_id = client.get("/api/auth/me", headers=auth).json()["id"]
    now = datetime.now(timezone.utc)
    old = jwt.encode({"sub": str(user_id), "iat": int(time.time()) - 600, "exp": now + timedelta(hours=1)},
                     settings.secret_key, algorithm="HS256")  # emitida hace 10 minutos
    assert client.get("/api/auth/me", headers=hdr(old)).status_code == 200
    client.post("/api/account/password", headers=auth, json={"current_password": "12345678", "new_password": "nueva-clave-99"})
    r = client.get("/api/auth/me", headers=hdr(old))
    assert r.status_code == 401 and "contraseña cambió" in r.json()["detail"]


def test_change_password_validations(client, auth):
    url = "/api/account/password"
    assert client.post(url, headers=auth, json={"current_password": "mala", "new_password": "nueva-clave-99"}).status_code == 403
    assert client.post(url, headers=auth, json={"current_password": "12345678", "new_password": "corta"}).status_code == 422
    assert client.post(url, headers=auth, json={"current_password": "12345678", "new_password": "12345678"}).status_code == 422
    assert client.post(url, json={"current_password": "12345678", "new_password": "nueva-clave-99"}).status_code == 401


def test_wrong_current_password_is_rate_limited(client, auth):
    url = "/api/account/password"
    for _ in range(5):
        assert client.post(url, headers=auth, json={"current_password": "mala", "new_password": "nueva-clave-99"}).status_code == 403
    assert client.post(url, headers=auth, json={"current_password": "12345678", "new_password": "nueva-clave-99"}).status_code == 429


# ---------------------------------------------------------------- exportar
def seed(client, auth, bank):
    client.post("/api/transactions", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": "1234.56",
                                                         "date": TODAY, "note": "Almuerzo", "tags": ["trabajo"]})
    client.post("/api/savings", headers=auth, json={"name": "Viaje", "target_amount": 500000, "current_amount": 1000,
                                                    "target_date": (clock_today() + timedelta(days=90)).isoformat()})
    client.post("/api/loans", headers=auth, json={"person": "Ana", "direction": "lent", "amount": 5000, "date": TODAY})
    client.post("/api/debts", headers=auth, json={"name": "Moto", "kind": "loan", "original_amount": 100, "current_balance": 100,
                                                  "rate": 10, "term_months": 12})


def test_export_contains_everything_and_no_secrets(client, auth, bank):
    seed(client, auth, bank)
    r = client.get("/api/account/export", headers=auth)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert r.headers["cache-control"] == "no-store"
    data = json.loads(r.text)
    assert data["user"]["email"] == "t@t.co"
    assert "password" not in r.text.lower() and "password_hash" not in r.text
    assert len(data["accounts"]) == 1 and len(data["transactions"]) == 1 and len(data["loans"]) == 1
    tx = data["transactions"][0]
    assert tx["amount"] == "1234.56" and tx["tags"] == ["trabajo"]  # decimales exactos, como texto
    assert data["savings_contributions"][0]["note"] == "Saldo inicial"
    assert len(data["categories"]) == 9 and len(data["debts"]) == 1


def test_export_only_includes_my_data_and_requires_login(client, auth, bank):
    seed(client, auth, bank)
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    other = hdr(client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"])
    data = json.loads(client.get("/api/account/export", headers=other).text)
    assert data["transactions"] == [] and data["accounts"] == [] and data["loans"] == []
    assert client.get("/api/account/export").status_code == 401


# ---------------------------------------------------------------- borrar cuenta
def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_delete_account_removes_everything_including_files(client, auth, bank):
    seed(client, auth, bank)
    tx = client.get("/api/transactions", headers=auth).json()[0]
    client.post(f"/api/transactions/{tx['id']}/attachments", headers=auth, files={"file": ("r.png", PNG, "image/png")})
    client.post("/api/loans", headers=auth, json={"person": "Luis", "direction": "borrowed", "amount": 900, "date": TODAY, "account_id": bank["id"]})
    client.post("/api/recurring", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": 5, "start_date": "2099-01-01"})
    client.post("/api/accounts", headers=auth, json={"name": "Visa", "type": "credit_card", "institution": "bbva",
                                                     "initial_balance": 10, "credit_limit": 1000})
    assert [p for p in Path(settings.upload_dir).rglob("*") if p.is_file()]

    r = client.post("/api/account/delete", headers=auth, json={"password": "12345678"})
    assert r.status_code == 204
    assert client.get("/api/auth/me", headers=auth).status_code == 401
    assert login(client).status_code == 401
    assert [p for p in Path(settings.upload_dir).rglob("*") if p.is_file()] == []


def test_delete_account_leaves_other_users_untouched(client, auth, bank):
    seed(client, auth, bank)
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    other = hdr(client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"])
    acc = client.post("/api/accounts", headers=other, json={"name": "Suya", "type": "cash", "initial_balance": 50}).json()
    client.post("/api/transactions", headers=other, json={"account_id": acc["id"], "kind": "expense", "amount": 5, "date": TODAY, "tags": ["suya"]})

    assert client.post("/api/account/delete", headers=auth, json={"password": "12345678"}).status_code == 204
    assert len(client.get("/api/transactions", headers=other).json()) == 1
    assert client.get("/api/tags", headers=other).json()[0]["name"] == "suya"
    assert len(client.get("/api/categories", headers=other).json()) == 9


def test_delete_account_needs_the_right_password(client, auth, bank):
    assert client.post("/api/account/delete", headers=auth, json={"password": "equivocada"}).status_code == 403
    assert client.get("/api/auth/me", headers=auth).status_code == 200  # sigue existiendo
    assert client.post("/api/account/delete", json={"password": "12345678"}).status_code == 401
