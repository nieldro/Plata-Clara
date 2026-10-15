from datetime import date

from app.services.rules import fold, tokens
from conftest import category_id


def add(client, auth, account, note, category=None, kind="expense", amount=1000):
    r = client.post("/api/transactions", headers=auth, json={
        "account_id": account["id"], "category_id": category, "kind": kind, "amount": amount,
        "note": note, "date": date.today().isoformat()})
    assert r.status_code == 201
    return r.json()


def suggest(client, auth, text, kind=None):
    params = {"text": text, **({"kind": kind} if kind else {})}
    return client.get("/api/categorize", headers=auth, params=params).json()["suggestion"]


def test_fold_and_tokens():
    assert fold("ÉXITO Cra. 7ª") == "exito cra. 7a"
    assert tokens("Compra ÉXITO Chapinero 123 PSE") == ["exito", "chapinero"]  # sin palabras vacías ni números
    assert tokens("a de la") == []


def test_learns_from_categorized_transactions(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    assert suggest(client, auth, "Éxito") is None
    add(client, auth, bank, "Éxito Calle 80", mercado)
    s = suggest(client, auth, "EXITO chapinero")
    assert s["category_id"] == mercado and "exito" in s["matched"]
    assert suggest(client, auth, "Taxi") is None


def test_no_suggestion_when_evidence_is_split(client, auth, bank):
    mercado, ocio = category_id(client, auth, "Mercado"), category_id(client, auth, "Ocio")
    add(client, auth, bank, "Rappi", mercado)
    add(client, auth, bank, "Rappi", ocio)
    assert suggest(client, auth, "rappi") is None
    add(client, auth, bank, "Rappi", mercado)
    add(client, auth, bank, "Rappi", mercado)  # 3 contra 1 → ya domina
    assert suggest(client, auth, "rappi")["category_id"] == mercado


def test_manual_rule_beats_learned_and_validates(client, auth, bank):
    mercado, ocio = category_id(client, auth, "Mercado"), category_id(client, auth, "Ocio")
    for _ in range(5):
        add(client, auth, bank, "Netflix", mercado)
    assert suggest(client, auth, "netflix")["category_id"] == mercado
    assert client.post("/api/rules", headers=auth, json={"keyword": "NETFLIX", "category_id": ocio}).status_code == 201
    assert suggest(client, auth, "netflix")["category_id"] == ocio
    assert client.post("/api/rules", headers=auth, json={"keyword": "dos palabras", "category_id": ocio}).status_code == 422
    assert client.post("/api/rules", headers=auth, json={"keyword": "123", "category_id": ocio}).status_code == 422
    assert client.post("/api/rules", headers=auth, json={"keyword": "algo", "category_id": 9999}).status_code == 404


def test_suggestion_respects_income_or_expense_kind(client, auth, bank):
    salario = category_id(client, auth, "Salario")
    add(client, auth, bank, "Nómina empresa", salario, kind="income")
    assert suggest(client, auth, "nomina", kind="income")["category_id"] == salario
    assert suggest(client, auth, "nomina", kind="expense") is None


def test_editing_category_teaches_and_deleting_rules_and_categories(client, auth, bank):
    tx = add(client, auth, bank, "Droguería Cruz")
    transporte = category_id(client, auth, "Salud")
    client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"category_id": transporte})
    assert suggest(client, auth, "drogueria")["category_id"] == transporte

    rules = client.get("/api/rules", headers=auth).json()
    assert {r["keyword"] for r in rules} >= {"drogueria", "cruz"}
    assert client.delete(f"/api/rules/{rules[0]['id']}", headers=auth).status_code == 204

    client.delete(f"/api/categories/{transporte}", headers=auth)
    assert client.get("/api/rules", headers=auth).json() == []


def test_rules_are_private(client, auth, bank):
    add(client, auth, bank, "Zapatería", category_id(client, auth, "Ocio"))
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/categorize", headers=other, params={"text": "zapateria"}).json()["suggestion"] is None
    assert client.get("/api/rules", headers=other).json() == []
