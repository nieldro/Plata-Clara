from datetime import date

from app.services.tags import normalize


def add(client, auth, account, amount, tags=None, kind="expense", note=""):
    body = {"account_id": account["id"], "kind": kind, "amount": amount, "note": note,
            "date": date.today().isoformat()}
    if tags is not None:
        body["tags"] = tags
    r = client.post("/api/transactions", headers=auth, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_normalize():
    assert normalize("  #Viaje   Cartagena ") == "viaje-cartagena"
    assert normalize("##") == ""
    assert normalize("Año--Nuevo") == "año-nuevo"


def test_create_with_tags_normalizes_and_dedupes(client, auth, bank):
    tx = add(client, auth, bank, 100, ["#Viaje Cartagena", "viaje-cartagena", "  ", "Regalo"])
    assert tx["tags"] == ["regalo", "viaje-cartagena"]
    assert client.get("/api/transactions", headers=auth).json()[0]["tags"] == ["regalo", "viaje-cartagena"]


def test_filter_by_tag_and_summary(client, auth, bank):
    add(client, auth, bank, 300_000, ["cartagena"], note="hotel")
    add(client, auth, bank, 80_000, ["cartagena", "comida"], note="cena")
    add(client, auth, bank, 5_000, [], note="otro")
    add(client, auth, bank, 40_000, ["cartagena"], kind="income", note="reembolso")

    got = client.get("/api/transactions", headers=auth, params={"tag": "#Cartagena"}).json()
    assert sorted(t["note"] for t in got) == ["cena", "hotel", "reembolso"]

    tags = {t["name"]: t for t in client.get("/api/tags", headers=auth).json()}
    assert tags["cartagena"]["count"] == 3
    assert float(tags["cartagena"]["expense"]) == 380_000 and float(tags["cartagena"]["income"]) == 40_000
    assert tags["comida"]["count"] == 1


def test_update_tags_replace_keep_and_clear(client, auth, bank):
    tx = add(client, auth, bank, 100, ["a", "b"])
    url = f"/api/transactions/{tx['id']}"
    assert client.patch(url, headers=auth, json={"tags": ["b", "c"]}).json()["tags"] == ["b", "c"]
    assert client.patch(url, headers=auth, json={"note": "x"}).json()["tags"] == ["b", "c"]  # no enviadas: no cambian
    assert client.patch(url, headers=auth, json={"tags": []}).json()["tags"] == []


def test_limits(client, auth, bank):
    body = {"account_id": bank["id"], "kind": "expense", "amount": 1, "date": date.today().isoformat()}
    assert client.post("/api/transactions", headers=auth, json={**body, "tags": [f"t{i}" for i in range(11)]}).status_code == 422
    assert client.post("/api/transactions", headers=auth, json={**body, "tags": ["x" * 31]}).status_code == 422


def test_delete_tag_keeps_transactions_and_delete_tx_keeps_tag(client, auth, bank):
    tx = add(client, auth, bank, 100, ["temp"])
    tag = client.get("/api/tags", headers=auth).json()[0]
    assert client.delete(f"/api/tags/{tag['id']}", headers=auth).status_code == 204
    assert client.get("/api/transactions", headers=auth).json()[0]["tags"] == []

    tx2 = add(client, auth, bank, 100, ["otra"])
    client.delete(f"/api/transactions/{tx2['id']}", headers=auth)
    assert [t["count"] for t in client.get("/api/tags", headers=auth).json()] == [0]


def test_tags_are_private_per_user(client, auth, bank):
    add(client, auth, bank, 100, ["secreta"])
    tag = client.get("/api/tags", headers=auth).json()[0]
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/tags", headers=other).json() == []
    assert client.delete(f"/api/tags/{tag['id']}", headers=other).status_code == 404
    assert client.get("/api/transactions", headers=other, params={"tag": "secreta"}).json() == []
