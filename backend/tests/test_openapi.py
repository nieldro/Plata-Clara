from app.main import docs_urls


def test_docs_are_served_in_development(client):
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "Plata Clara"
    assert "Bearer" in spec["info"]["description"]


def test_docs_are_hidden_in_production():
    urls = docs_urls("production")
    assert urls == {"docs_url": None, "redoc_url": None, "openapi_url": None}
    assert docs_urls("development")["openapi_url"] == "/openapi.json"
