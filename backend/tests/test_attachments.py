import io
from pathlib import Path

from app.config import settings

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPG = b"\xff\xd8\xff\xe0" + b"1" * 64
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"2" * 32
PDF = b"%PDF-1.7\n" + b"3" * 64


def tx(client, auth, account):
    return client.post("/api/transactions", headers=auth, json={
        "account_id": account["id"], "kind": "expense", "amount": 1000, "date": "2026-03-01"}).json()


def upload(client, auth, tx_id, content=PNG, name="recibo.png", ctype="image/png"):
    return client.post(f"/api/transactions/{tx_id}/attachments", headers=auth, files={"file": (name, content, ctype)})


def files_on_disk():
    return [p for p in Path(settings.upload_dir).rglob("*") if p.is_file()]


def test_upload_list_download_roundtrip(client, auth, bank):
    t = tx(client, auth, bank)
    r = upload(client, auth, t["id"])
    assert r.status_code == 201
    att = r.json()
    assert att["content_type"] == "image/png" and att["size"] == len(PNG) and att["filename"] == "recibo.png"
    assert client.get(f"/api/transactions/{t['id']}/attachments", headers=auth).json()[0]["id"] == att["id"]

    dl = client.get(f"/api/attachments/{att['id']}/file", headers=auth)
    assert dl.status_code == 200 and dl.content == PNG
    assert dl.headers["content-type"] == "image/png" and dl.headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/transactions", headers=auth).json()[0]["attachments"] == 1


def test_accepts_all_supported_types_and_ignores_declared_type(client, auth, bank):
    t = tx(client, auth, bank)
    for content, ext, expected in [(JPG, "jpg", "image/jpeg"), (WEBP, "webp", "image/webp"), (PDF, "pdf", "application/pdf")]:
        r = upload(client, auth, t["id"], content, f"x.{ext}", "application/octet-stream")
        assert r.status_code == 201 and r.json()["content_type"] == expected


def test_rejects_disguised_empty_and_oversized_files(client, auth, bank):
    t = tx(client, auth, bank)
    assert upload(client, auth, t["id"], b"<script>alert(1)</script>", "foto.png", "image/png").status_code == 415
    assert upload(client, auth, t["id"], b"MZ\x90\x00 programa.exe", "recibo.pdf", "application/pdf").status_code == 415
    assert upload(client, auth, t["id"], b"", "vacio.png").status_code == 422
    big = PNG + b"0" * (settings.max_upload_mb * 1024 * 1024)
    assert upload(client, auth, t["id"], big).status_code == 413
    assert files_on_disk() == [] or all(p.stat().st_size <= len(PNG) + 1 for p in files_on_disk())


def test_limit_of_five_per_transaction(client, auth, bank):
    t = tx(client, auth, bank)
    for _ in range(5):
        assert upload(client, auth, t["id"]).status_code == 201
    assert upload(client, auth, t["id"]).status_code == 422


def test_malicious_filename_never_reaches_the_disk(client, auth, bank):
    t = tx(client, auth, bank)
    r = upload(client, auth, t["id"], PNG, "../../../etc/passwd\x00.png")
    assert r.status_code == 201
    assert "/" not in r.json()["filename"] and "\x00" not in r.json()["filename"]
    root = Path(settings.upload_dir).resolve()
    assert all(root in p.resolve().parents for p in files_on_disk())


def test_files_are_private_between_users(client, auth, bank):
    t = tx(client, auth, bank)
    att = upload(client, auth, t["id"]).json()
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    assert client.get(f"/api/attachments/{att['id']}/file", headers=other).status_code == 404
    assert client.delete(f"/api/attachments/{att['id']}", headers=other).status_code == 404
    assert client.get(f"/api/transactions/{t['id']}/attachments", headers=other).status_code == 404
    assert upload(client, other, t["id"]).status_code == 404
    assert client.get(f"/api/attachments/{att['id']}/file").status_code == 401  # sin sesión


def test_delete_attachment_removes_file(client, auth, bank):
    t = tx(client, auth, bank)
    att = upload(client, auth, t["id"]).json()
    assert len(files_on_disk()) == 1
    assert client.delete(f"/api/attachments/{att['id']}", headers=auth).status_code == 204
    assert files_on_disk() == []
    assert client.get(f"/api/attachments/{att['id']}/file", headers=auth).status_code == 404


def test_deleting_transaction_or_account_removes_files_and_rows(client, auth, bank):
    t1 = tx(client, auth, bank)
    upload(client, auth, t1["id"])
    assert client.delete(f"/api/transactions/{t1['id']}", headers=auth).status_code == 204
    assert files_on_disk() == []

    t2 = tx(client, auth, bank)
    upload(client, auth, t2["id"])
    client.patch(f"/api/transactions/{t2['id']}", headers=auth, json={"tags": ["viaje"]})
    client.post("/api/recurring", headers=auth, json={"account_id": bank["id"], "kind": "expense", "amount": 5,
                                                      "start_date": "2099-01-01"})
    assert client.delete(f"/api/accounts/{bank['id']}", headers=auth).status_code == 204  # con llaves foráneas activas
    assert files_on_disk() == []
    assert client.get("/api/recurring", headers=auth).json() == []
