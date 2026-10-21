def save(client, auth, name="Gastos de Nequi", **params):
    return client.post("/api/saved-filters", headers=auth, json={"name": name, "params": params or {"kind": "expense", "min_amount": "100000"}})


def names(client, auth):
    return [f["name"] for f in client.get("/api/saved-filters", headers=auth).json()]


def test_save_list_and_delete(client, auth):
    r = save(client, auth, "Gastos grandes", kind="expense", min_amount="100000", tag="viaje")
    assert r.status_code == 201
    saved = r.json()
    assert saved["name"] == "Gastos grandes" and saved["params"] == {"kind": "expense", "min_amount": "100000", "tag": "viaje"}
    assert client.get("/api/saved-filters", headers=auth).json() == [saved]
    assert client.delete(f"/api/saved-filters/{saved['id']}", headers=auth).status_code == 204
    assert client.get("/api/saved-filters", headers=auth).json() == []
    assert client.delete(f"/api/saved-filters/{saved['id']}", headers=auth).status_code == 404


def test_same_name_replaces_ignoring_case_and_spacing(client, auth):
    first = save(client, auth, "Mercado", category="3").json()
    again = save(client, auth, "  mercado ", q="éxito")
    assert again.status_code == 201 and again.json()["id"] == first["id"] and again.json()["params"] == {"q": "éxito"}
    assert names(client, auth) == ["Mercado"]


def test_accents_and_empty_values_are_handled(client, auth):
    r = save(client, auth, "Cafés", q="café", tag="", kind="  ", min_amount="5000").json()
    assert r["params"] == {"q": "café", "min_amount": "5000"}      # los vacíos se descartan, la tilde se conserva


def test_list_is_sorted_by_name_case_insensitively(client, auth):
    for n in ("beta", "Alfa", "gamma"):
        save(client, auth, n)
    assert names(client, auth) == ["Alfa", "beta", "gamma"]


def test_validation(client, auth):
    assert save(client, auth, "x", **{"kind": "expense", "inventado": "1"}).status_code == 422     # filtro desconocido
    assert client.post("/api/saved-filters", headers=auth, json={"name": "x", "params": {}}).status_code == 422
    assert client.post("/api/saved-filters", headers=auth, json={"name": "x", "params": {"q": "  "}}).status_code == 422
    assert save(client, auth, "   ", q="a").status_code == 422
    assert save(client, auth, "n" * 61, q="a").status_code == 422
    assert save(client, auth, "ok", q="a" * 101).status_code == 422
    assert client.post("/api/saved-filters", headers=auth, json={"name": "x"}).status_code == 422
    assert client.post("/api/saved-filters", json={"name": "x", "params": {"q": "a"}}).status_code == 401


def test_limit_of_thirty_views(client, auth):
    for i in range(30):
        assert save(client, auth, f"vista {i}", q="a").status_code == 201
    r = save(client, auth, "una más", q="a")
    assert r.status_code == 422 and "hasta 30" in r.json()["detail"]
    assert save(client, auth, "VISTA 3", q="b").status_code == 201        # reemplazar una existente sí se puede
    assert len(names(client, auth)) == 30


def test_views_are_private(client, auth):
    mine = save(client, auth, "Mía").json()
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/saved-filters", headers=other).json() == []
    assert client.delete(f"/api/saved-filters/{mine['id']}", headers=other).status_code == 404
    assert client.post("/api/saved-filters", headers=other, json={"name": "Mía", "params": {"q": "x"}}).status_code == 201  # mismo nombre, otra persona
    assert names(client, auth) == ["Mía"]


def test_account_deletion_removes_views(client, auth):
    save(client, auth)
    assert client.post("/api/account/delete", headers=auth, json={"password": "12345678"}).status_code == 204
