def create(client, auth, name, kind="expense"):
    return client.post("/api/categories", headers=auth, json={"name": name, "kind": kind})


def test_duplicate_name_is_rejected_ignoring_case_and_spacing(client, auth):
    assert create(client, auth, "Mascotas").status_code == 201
    assert create(client, auth, "mascotas").status_code == 409
    assert create(client, auth, "  MASCOTAS  ").status_code == 409
    r = create(client, auth, "Mascotas")
    assert r.status_code == 409 and "«Mascotas»" in r.json()["detail"] and "de gasto" in r.json()["detail"]


def test_default_categories_cannot_be_duplicated(client, auth):
    assert create(client, auth, "Mercado").status_code == 409
    assert create(client, auth, "salario", "income").status_code == 409


def test_same_name_is_allowed_for_income_and_expense(client, auth):
    assert create(client, auth, "Otros").status_code == 201          # gasto
    assert create(client, auth, "Otros", "income").status_code == 201  # ingreso: es otra cosa
    assert create(client, auth, "Otros", "income").status_code == 409


def test_blank_name_is_rejected_and_name_is_trimmed(client, auth):
    assert create(client, auth, "   ").status_code == 422
    assert create(client, auth, "").status_code == 422
    assert create(client, auth, "x" * 101).status_code == 422
    assert create(client, auth, "  Regalos  ").json()["name"] == "Regalos"


def test_two_users_can_have_the_same_category_name(client, auth):
    create(client, auth, "Hobby")
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    assert client.post("/api/categories", headers=other, json={"name": "Hobby", "kind": "expense"}).status_code == 201


def rename(client, auth, cid, name):
    return client.patch(f"/api/categories/{cid}", headers=auth, json={"name": name})


def test_rename_keeps_transactions_budgets_and_learned_rules(client, auth, bank):
    from conftest import category_id
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 300_000})
    client.post("/api/transactions", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": 5_000,
                                                         "note": "Éxito", "category_id": mercado, "date": "2026-03-01"})
    r = rename(client, auth, mercado, "  Supermercado ")
    assert r.status_code == 200 and r.json() == {"id": mercado, "name": "Supermercado", "kind": "expense"}
    assert client.get("/api/budgets", headers=auth).json()["items"][0]["category"] == "Supermercado"
    assert client.get("/api/transactions", headers=auth).json()[0]["category_id"] == mercado
    assert client.get("/api/categorize", headers=auth, params={"text": "exito"}).json()["suggestion"]["category_id"] == mercado


def test_rename_to_an_existing_name_is_rejected_but_own_name_and_case_change_are_fine(client, auth):
    a = create(client, auth, "Mascotas").json()["id"]
    create(client, auth, "Hobby")
    assert rename(client, auth, a, "hobby").status_code == 409
    assert rename(client, auth, a, "Mascotas").status_code == 200       # el mismo nombre no choca consigo mismo
    assert rename(client, auth, a, "MASCOTAS").status_code == 200       # solo cambiar mayúsculas tampoco
    create(client, auth, "Hobby", "income")
    assert rename(client, auth, a, "Hobby").status_code == 409          # choca con la de gasto, no con la de ingreso


def test_rename_validation_and_ownership(client, auth):
    a = create(client, auth, "Mascotas").json()["id"]
    assert rename(client, auth, a, "   ").status_code == 422
    assert rename(client, auth, a, "x" * 101).status_code == 422
    assert client.patch(f"/api/categories/{a}", headers=auth, json={}).status_code == 422
    assert rename(client, auth, 9999, "Algo").status_code == 404
    assert client.patch(f"/api/categories/{a}", json={"name": "Algo"}).status_code == 401
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    assert client.patch(f"/api/categories/{a}", headers={"Authorization": f"Bearer {tok}"}, json={"name": "Hack"}).status_code == 404


def test_deleted_category_name_can_be_reused(client, auth):
    cid = create(client, auth, "Temporal").json()["id"]
    assert client.delete(f"/api/categories/{cid}", headers=auth).status_code == 204
    assert create(client, auth, "Temporal").status_code == 201
