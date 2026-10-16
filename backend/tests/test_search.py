from datetime import date, timedelta
from app.clock import today as clock_today

from conftest import category_id


def add(client, auth, account, amount, note="", kind="expense", day=None, category=None):
    r = client.post("/api/transactions", headers=auth, json={
        "account_id": account["id"], "category_id": category, "kind": kind, "amount": amount,
        "note": note, "date": (day or clock_today()).isoformat()})
    assert r.status_code == 201


def search(client, auth, **params):
    r = client.get("/api/transactions", headers=auth, params=params)
    assert r.status_code == 200
    return r


def notes(r):
    return sorted(t["note"] for t in r.json())


def seed(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    add(client, auth, bank, 50_000, "Éxito mercado", category=mercado)
    add(client, auth, bank, 12_000, "Taxi al aeropuerto")
    add(client, auth, bank, 3_000_000, "Nómina", kind="income", day=clock_today() - timedelta(days=40))
    return mercado


def test_text_search_matches_note_case_insensitive(client, auth, bank):
    seed(client, auth, bank)
    assert notes(search(client, auth, q="TAXI")) == ["Taxi al aeropuerto"]
    assert notes(search(client, auth, q="  éxito ")) == ["Éxito mercado"]


def test_text_search_also_matches_category_name(client, auth, bank):
    seed(client, auth, bank)
    assert notes(search(client, auth, q="mercado")) == ["Éxito mercado"]
    client.post("/api/categories", headers=auth, json={"name": "Aeropuerto", "kind": "expense"})
    assert notes(search(client, auth, q="aeropuerto")) == ["Taxi al aeropuerto"]


def test_amount_range(client, auth, bank):
    seed(client, auth, bank)
    assert notes(search(client, auth, min_amount=20_000, max_amount=100_000)) == ["Éxito mercado"]
    assert len(search(client, auth, min_amount=100_000).json()) == 1


def test_date_range_and_kind(client, auth, bank):
    seed(client, auth, bank)
    recent = (clock_today() - timedelta(days=7)).isoformat()
    assert len(search(client, auth, date_from=recent).json()) == 2
    assert notes(search(client, auth, kind="income")) == ["Nómina"]
    assert search(client, auth, date_to=(clock_today() - timedelta(days=30)).isoformat()).json()[0]["note"] == "Nómina"


def test_category_and_uncategorized_filters(client, auth, bank):
    mercado = seed(client, auth, bank)
    assert notes(search(client, auth, category_id=mercado)) == ["Éxito mercado"]
    assert notes(search(client, auth, uncategorized=True)) == ["Nómina", "Taxi al aeropuerto"]


def test_pagination_and_total_header(client, auth, bank):
    for i in range(5):
        add(client, auth, bank, 1_000 + i, f"mov {i}")
    r = search(client, auth, limit=2, offset=2)
    assert len(r.json()) == 2 and r.headers["x-total-count"] == "5"
    assert search(client, auth, limit=2, offset=4).json()[0]["note"] == "mov 0"  # más antiguos al final


def test_hide_transfers(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={
        "name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    client.post("/api/transfers", headers=auth, json={
        "from_account_id": bank["id"], "to_account_id": other["id"], "amount": 5, "date": clock_today().isoformat()})
    add(client, auth, bank, 100, "normal")
    assert len(search(client, auth).json()) == 3
    assert notes(search(client, auth, hide_transfers=True)) == ["normal"]


def test_invalid_ranges_rejected_and_isolation(client, auth, bank):
    seed(client, auth, bank)
    assert client.get("/api/transactions", headers=auth,
                      params={"date_from": "2026-12-31", "date_to": "2026-01-01"}).status_code == 422
    assert client.get("/api/transactions", headers=auth, params={"min_amount": 10, "max_amount": 5}).status_code == 422
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    assert client.get("/api/transactions", headers={"Authorization": f"Bearer {tok}"}, params={"q": "taxi"}).json() == []
