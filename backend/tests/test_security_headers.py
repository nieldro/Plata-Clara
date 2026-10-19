PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def test_every_response_carries_the_security_headers(client, auth):
    for path, headers in (("/health", {}), ("/api/auth/me", auth), ("/api/accounts", auth)):
        h = client.get(path, headers=headers).headers
        assert h["x-content-type-options"] == "nosniff"
        assert h["x-frame-options"] == "DENY"
        assert h["referrer-policy"] == "no-referrer"


def test_errors_also_carry_them(client):
    r = client.get("/api/auth/me")  # 401 sin sesión
    assert r.status_code == 401 and r.headers["x-content-type-options"] == "nosniff"
    assert client.get("/ruta-que-no-existe").headers["x-frame-options"] == "DENY"  # 404


def test_private_api_data_is_not_cacheable(client, auth):
    assert client.get("/api/accounts", headers=auth).headers["cache-control"] == "no-store"
    assert client.get("/api/auth/me").headers["cache-control"] == "no-store"
    assert "cache-control" not in client.get("/health").headers  # lo que no es de la API no se toca


def test_endpoints_with_their_own_cache_policy_keep_it(client, auth, bank):
    tx = client.post("/api/transactions", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": 1,
                                                              "date": "2026-03-01"}).json()
    att = client.post(f"/api/transactions/{tx['id']}/attachments", headers=auth,
                      files={"file": ("r.png", PNG, "image/png")}).json()
    dl = client.get(f"/api/attachments/{att['id']}/file", headers=auth)
    assert dl.headers["cache-control"] == "private, max-age=3600"  # el recibo sí se puede guardar en TU navegador
    assert dl.headers["x-content-type-options"] == "nosniff"
    export = client.get("/api/export/transactions", headers=auth, params={"format": "csv"})
    assert export.headers["cache-control"] == "no-store"
