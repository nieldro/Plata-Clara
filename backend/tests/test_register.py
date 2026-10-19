def register(client, email="ana@correo.co", name="Ana", password="12345678"):
    return client.post("/api/auth/register", json={"email": email, "password": password, "name": name})


def login(client, email, password="12345678"):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def test_email_and_name_are_trimmed_and_lowercased(client):
    r = register(client, "  Ana@Correo.CO  ", "  Ana María  ")
    assert r.status_code == 201
    assert r.json()["email"] == "ana@correo.co" and r.json()["name"] == "Ana María"


def test_same_email_in_other_case_or_spacing_is_a_duplicate(client):
    assert register(client).status_code == 201
    for variant in ("ANA@correo.co", " ana@correo.co", "Ana@Correo.Co "):
        assert register(client, variant).status_code == 409


def test_login_accepts_any_case_and_surrounding_spaces(client):
    register(client)
    assert login(client, "ANA@CORREO.CO").status_code == 200
    assert login(client, "  ana@correo.co ").status_code == 200


def test_blank_name_or_invalid_email_is_rejected(client):
    assert register(client, name="   ").status_code == 422
    assert register(client, name="").status_code == 422
    assert register(client, email="no-es-un-correo").status_code == 422
    assert register(client, email="").status_code == 422
    assert register(client, password="corta").status_code == 422
