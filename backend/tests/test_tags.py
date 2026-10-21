from app.clock import today as clock_today

from app.services.tags import normalize


def add(client, auth, account, amount, tags=None, kind="expense", note=""):
    body = {"account_id": account["id"], "kind": kind, "amount": amount, "note": note,
            "date": clock_today().isoformat()}
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
    body = {"account_id": bank["id"], "kind": "expense", "amount": 1, "date": clock_today().isoformat()}
    assert client.post("/api/transactions", headers=auth, json={**body, "tags": [f"t{i}" for i in range(11)]}).status_code == 422
    assert client.post("/api/transactions", headers=auth, json={**body, "tags": ["x" * 31]}).status_code == 422


def test_delete_tag_keeps_transactions_and_delete_tx_keeps_tag(client, auth, bank):
    add(client, auth, bank, 100, ["temp"])
    tag = client.get("/api/tags", headers=auth).json()[0]
    assert client.delete(f"/api/tags/{tag['id']}", headers=auth).status_code == 204
    assert client.get("/api/transactions", headers=auth).json()[0]["tags"] == []

    tx2 = add(client, auth, bank, 100, ["otra"])
    client.delete(f"/api/transactions/{tx2['id']}", headers=auth)
    assert [t["count"] for t in client.get("/api/tags", headers=auth).json()] == [0]


def tag_id(client, auth, name):
    return next(t["id"] for t in client.get("/api/tags", headers=auth).json() if t["name"] == name)


def rename(client, auth, tid, name):
    return client.patch(f"/api/tags/{tid}", headers=auth, json={"name": name})


def test_rename_a_tag_everywhere(client, auth, bank):
    add(client, auth, bank, 100, ["viaje"])
    r = rename(client, auth, tag_id(client, auth, "viaje"), "  #Viaje Cartagena ")
    assert r.json()["name"] == "viaje-cartagena" and r.json()["merged"] is False
    assert client.get("/api/transactions", headers=auth).json()[0]["tags"] == ["viaje-cartagena"]
    assert rename(client, auth, tag_id(client, auth, "viaje-cartagena"), "VIAJE-cartagena").json()["moved"] == 0  # mismo nombre


def test_renaming_into_an_existing_tag_merges_without_duplicates(client, auth, bank):
    only_a = add(client, auth, bank, 100, ["viaje"])["id"]
    both = add(client, auth, bank, 200, ["viaje", "viajes"])["id"]
    only_b = add(client, auth, bank, 300, ["viajes"])["id"]
    r = rename(client, auth, tag_id(client, auth, "viaje"), "viajes").json()
    assert r["merged"] is True and r["name"] == "viajes" and r["moved"] == 1   # solo «only_a» necesitaba moverse
    tags = client.get("/api/tags", headers=auth).json()
    assert [(t["name"], t["count"]) for t in tags] == [("viajes", 3)]          # «viaje» desapareció y nadie quedó repetido
    by_id = {t["id"]: t["tags"] for t in client.get("/api/transactions", headers=auth).json()}
    assert by_id == {only_a: ["viajes"], both: ["viajes"], only_b: ["viajes"]}


def test_merge_never_goes_over_the_ten_tag_limit(client, auth, bank):
    names = [f"t{i}" for i in range(9)]
    full = add(client, auth, bank, 1, [*names, "viejo"])["id"]   # 9 + 1 = 10 etiquetas, el máximo
    add(client, auth, bank, 1, ["nuevo"])
    rename(client, auth, tag_id(client, auth, "viejo"), "nuevo")
    tags = {t["id"]: t["tags"] for t in client.get("/api/transactions", headers=auth).json()}
    assert len(tags[full]) == 10 and "nuevo" in tags[full] and "viejo" not in tags[full]  # cambió una por otra: sigue en 10


def test_rename_validation_and_privacy(client, auth, bank):
    add(client, auth, bank, 100, ["mia"])
    tid = tag_id(client, auth, "mia")
    assert rename(client, auth, tid, "  # ").status_code == 422
    assert rename(client, auth, tid, "x" * 31).status_code == 422
    assert client.patch(f"/api/tags/{tid}", headers=auth, json={}).status_code == 422
    assert rename(client, auth, 9999, "otra").status_code == 404
    assert client.patch(f"/api/tags/{tid}", json={"name": "otra"}).status_code == 401
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    assert client.patch(f"/api/tags/{tid}", headers={"Authorization": f"Bearer {tok}"}, json={"name": "hack"}).status_code == 404


def test_tags_are_private_per_user(client, auth, bank):
    add(client, auth, bank, 100, ["secreta"])
    tag = client.get("/api/tags", headers=auth).json()[0]
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/tags", headers=other).json() == []
    assert client.delete(f"/api/tags/{tag['id']}", headers=other).status_code == 404
    assert client.get("/api/transactions", headers=other, params={"tag": "secreta"}).json() == []
