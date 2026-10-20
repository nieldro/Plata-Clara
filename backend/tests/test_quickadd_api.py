from datetime import timedelta

from app.clock import today as clock_today
from conftest import category_id

TODAY = clock_today()


def parse(client, auth, text):
    r = client.post("/api/quick-add/parse", headers=auth, json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def account(client, auth, name, institution="bancolombia", type_="savings", balance=0, **extra):
    r = client.post("/api/accounts", headers=auth, json={"name": name, "type": type_, "institution": institution,
                                                         "initial_balance": balance, **extra})
    assert r.status_code == 201
    return r.json()


def test_full_sentence_resolves_amount_date_account_and_tags(client, auth):
    account(client, auth, "Ahorros", "bancolombia")
    nequi = account(client, auth, "Mi billetera", "nequi", "wallet")
    r = parse(client, auth, "Almuerzo 18.500 ayer con Nequi #trabajo")
    assert r["ready"] is True and float(r["amount"]) == 18_500 and r["kind"] == "expense"
    assert r["date"] == (TODAY - timedelta(days=1)).isoformat()
    assert r["account_id"] == nequi["id"] and r["account_name"] == "Mi billetera"
    assert r["tags"] == ["trabajo"] and r["note"] == "Almuerzo" and r["warnings"] == []


def test_single_account_is_used_without_being_named(client, auth, bank):
    r = parse(client, auth, "café 4500")
    assert r["account_id"] == bank["id"]


def test_several_accounts_and_no_mention_leaves_account_empty(client, auth, bank):
    account(client, auth, "Otra", "nequi", "wallet")
    r = parse(client, auth, "café 4500")
    assert r["account_id"] is None and r["ready"] is True


def test_category_is_suggested_from_what_the_user_has_learned(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    client.post("/api/transactions", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": 9_000,
                                                         "note": "Éxito Calle 80", "category_id": mercado, "date": TODAY.isoformat()})
    r = parse(client, auth, "exito chapinero 62.000")
    assert r["category_id"] == mercado and r["category_confidence"] >= 0.6
    assert parse(client, auth, "taxi 12.000")["category_id"] is None


def test_income_sentence_gets_income_suggestion_kind(client, auth, bank):
    salario = category_id(client, auth, "Salario")
    client.post("/api/transactions", headers=auth, json={"account_id": bank["id"], "kind": "income", "amount": 1,
                                                         "note": "Nómina empresa", "category_id": salario, "date": TODAY.isoformat()})
    r = parse(client, auth, "nómina empresa 3.000.000")
    assert r["kind"] == "income" and r["category_id"] == salario and float(r["amount"]) == 3_000_000


def test_ambiguous_account_names_are_not_guessed(client, auth):
    account(client, auth, "Ahorros", "bancolombia")
    account(client, auth, "Corriente", "bancolombia", "checking")
    r = parse(client, auth, "mercado 80.000 con bancolombia")
    assert r["account_id"] is None and any("varias cuentas" in w for w in r["warnings"])


def test_missing_amount_is_not_ready(client, auth, bank):
    r = parse(client, auth, "algo sin monto")
    assert r["ready"] is False and r["amount"] is None and any("monto" in w for w in r["warnings"])
    assert parse(client, auth, "   ")["ready"] is False


def test_validation_auth_and_privacy(client, auth, bank):
    assert client.post("/api/quick-add/parse", headers=auth, json={"text": "x" * 301}).status_code == 422
    assert client.post("/api/quick-add/parse", headers=auth, json={}).status_code == 422
    assert client.post("/api/quick-add/parse", json={"text": "café 4500"}).status_code == 401
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = parse(client, {"Authorization": f"Bearer {tok}"}, "café 4500 con bancolombia")
    assert other["account_id"] is None   # no ve las cuentas de otro usuario


def test_parsing_never_creates_anything(client, auth, bank):
    parse(client, auth, "café 4500 ayer #viaje")
    assert client.get("/api/transactions", headers=auth).json() == []
    assert client.get("/api/tags", headers=auth).json() == []
