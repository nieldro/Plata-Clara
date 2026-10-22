def test_large_responses_are_compressed(client):
    r = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers["content-encoding"] == "gzip"
    assert r.json()["info"]["title"] == "Plata Clara"  # y el cliente la recibe íntegra


def test_small_responses_are_left_alone(client):
    r = client.get("/health", headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in r.headers


def test_clients_without_gzip_get_plain_json(client):
    r = client.get("/openapi.json", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in r.headers
