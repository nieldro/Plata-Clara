from app.clock import today as clock_today
from conftest import category_id

TODAY = clock_today().isoformat()
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def add(client, auth, account, amount=1_000, kind="expense", note="x", category=None, tags=None):
    r = client.post("/api/transactions", headers=auth, json={"account_id": account["id"], "kind": kind, "amount": amount,
                                                             "note": note, "date": TODAY, "category_id": category, "tags": tags or []})
    assert r.status_code == 201
    return r.json()["id"]


def bulk(client, auth, ids, action, **extra):
    return client.post("/api/transactions/bulk", headers=auth, json={"ids": ids, "action": action, **extra})


def listing(client, auth):
    return {t["id"]: t for t in client.get("/api/transactions", headers=auth).json()}


def balance(client, auth):
    return float(client.get("/api/accounts", headers=auth).json()[0]["balance"])


def test_delete_many_updates_the_balance(client, auth, bank):
    ids = [add(client, auth, bank, 100_000) for _ in range(3)]
    keep = add(client, auth, bank, 5_000)
    r = bulk(client, auth, ids, "delete")
    assert r.status_code == 200 and r.json() == {"action": "delete", "affected": 3, "skipped": [], "not_found": []}
    assert list(listing(client, auth)) == [keep] and balance(client, auth) == 1_000_000 - 5_000


def test_delete_reverts_credit_card_debt_and_removes_receipts(client, auth):
    card = client.post("/api/accounts", headers=auth, json={"name": "Visa", "type": "credit_card", "institution": "bbva",
                                                            "initial_balance": 100_000, "credit_limit": 1_000_000}).json()
    a, b = add(client, auth, card, 30_000), add(client, auth, card, 20_000)
    client.post(f"/api/transactions/{a}/attachments", headers=auth, files={"file": ("r.png", PNG, "image/png")})
    assert float(client.get("/api/debts", headers=auth).json()[0]["current_balance"]) == 150_000
    assert bulk(client, auth, [a, b], "delete").json()["affected"] == 2
    assert float(client.get("/api/debts", headers=auth).json()[0]["current_balance"]) == 100_000


def test_set_category_and_clear_it(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    ids = [add(client, auth, bank, note="Éxito Calle 80") for _ in range(2)]
    assert bulk(client, auth, ids, "set_category", category_id=mercado).json()["affected"] == 2
    assert {t["category_id"] for t in listing(client, auth).values()} == {mercado}
    assert client.get("/api/categorize", headers=auth, params={"text": "exito"}).json()["suggestion"]["category_id"] == mercado
    assert bulk(client, auth, ids, "set_category", clear_category=True).json()["affected"] == 2
    assert {t["category_id"] for t in listing(client, auth).values()} == {None}


def test_category_of_the_wrong_kind_is_skipped_with_a_reason(client, auth, bank):
    salario = category_id(client, auth, "Salario")
    gasto, ingreso = add(client, auth, bank), add(client, auth, bank, kind="income")
    r = bulk(client, auth, [gasto, ingreso], "set_category", category_id=salario).json()
    assert r["affected"] == 1 and r["skipped"] == [{"id": gasto, "reason": "la categoría es de otro tipo (ingreso/gasto)"}]


def test_add_and_remove_tag_creating_it_once(client, auth, bank):
    ids = [add(client, auth, bank) for _ in range(3)]
    assert bulk(client, auth, ids, "add_tag", tag="#Viaje Cartagena").json()["affected"] == 3   # etiqueta nueva, 3 movimientos
    tags = client.get("/api/tags", headers=auth).json()
    assert [(t["name"], t["count"]) for t in tags] == [("viaje-cartagena", 3)]                  # una sola etiqueta, no tres
    again = bulk(client, auth, ids, "add_tag", tag="viaje-cartagena").json()
    assert again["affected"] == 0 and {s["reason"] for s in again["skipped"]} == {"ya tenía esa etiqueta"}
    assert bulk(client, auth, ids[:2], "remove_tag", tag="viaje-cartagena").json()["affected"] == 2
    assert client.get("/api/tags", headers=auth).json()[0]["count"] == 1
    assert bulk(client, auth, ids[:2], "remove_tag", tag="viaje-cartagena").json()["affected"] == 0


def test_tag_limit_per_transaction_is_respected(client, auth, bank):
    full = add(client, auth, bank, tags=[f"t{i}" for i in range(10)])
    r = bulk(client, auth, [full], "add_tag", tag="una-mas").json()
    assert r["affected"] == 0 and "10 etiquetas" in r["skipped"][0]["reason"]


def test_transfers_and_loans_are_never_touched(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={"name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    client.post("/api/transfers", headers=auth, json={"from_account_id": bank["id"], "to_account_id": other["id"], "amount": 777, "date": TODAY})
    client.post("/api/loans", headers=auth, json={"person": "Ana", "direction": "lent", "amount": 555, "date": TODAY, "account_id": bank["id"]})
    locked = [t["id"] for t in client.get("/api/transactions", headers=auth).json()]
    assert len(locked) == 3
    r = bulk(client, auth, locked, "delete").json()
    assert r["affected"] == 0 and len(r["skipped"]) == 3 and len(client.get("/api/transactions", headers=auth).json()) == 3


def test_foreign_and_missing_ids_are_reported_not_applied(client, auth, bank):
    mine = add(client, auth, bank)
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    r = bulk(client, other, [mine, 9999], "delete", ).json()
    assert r["affected"] == 0 and r["not_found"] == [mine, 9999]
    assert mine in listing(client, auth)                                   # el movimiento de la otra persona sigue ahí
    assert bulk(client, other, [mine], "set_category", category_id=category_id(client, auth, "Mercado")).status_code == 404


def test_validation(client, auth, bank):
    one = add(client, auth, bank)
    assert bulk(client, auth, [], "delete").status_code == 422
    assert bulk(client, auth, list(range(1, 202)), "delete").status_code == 422
    assert bulk(client, auth, [one], "borrar").status_code == 422
    assert bulk(client, auth, [one], "set_category").status_code == 422
    assert bulk(client, auth, [one], "add_tag").status_code == 422
    assert bulk(client, auth, [one], "add_tag", tag="  # ").status_code == 422
    assert client.post("/api/transactions/bulk", json={"ids": [one], "action": "delete"}).status_code == 401
    assert one in listing(client, auth)
    assert bulk(client, auth, [one, one, one], "delete").json()["affected"] == 1   # repetidos cuentan una vez
