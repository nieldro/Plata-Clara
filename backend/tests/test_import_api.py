from datetime import date

from conftest import category_id

BANCOLOMBIA = (
    "Extracto de cuenta de ahorros;;;\n"
    "Titular;Daniel;;\n"
    "Fecha;Descripción;Valor;Saldo\n"
    "05/03/2026;COMPRA EXITO CHAPINERO;-50.000;950.000\n"
    "06/03/2026;PAGO NOMINA EMPRESA;3.000.000;3.950.000\n"
    "07/03/2026;Droguería Cruz Verde;-12.500;3.937.500\n"
    "07/03/2026;Droguería Cruz Verde;-12.500;3.925.000\n"
    "fecha mala;X;100;0\n"
).encode("cp1252")


def preview(client, auth, account, content=BANCOLOMBIA, name="extracto.csv", **form):
    return client.post("/api/imports/preview", headers=auth,
                       files={"file": (name, content, "text/csv")},
                       data={"account_id": str(account["id"]), **form})


def to_commit(rows, **overrides):
    return [{"date": r["date"], "description": r["description"], "amount": r["amount"], "kind": r["kind"],
             "category_id": r["category_id"], "import_hash": r["import_hash"], **overrides}
            for r in rows if not r["error"]]


def test_preview_detects_everything_and_saves_nothing(client, auth, bank):
    r = preview(client, auth, bank)
    assert r.status_code == 200
    body = r.json()
    assert body["header_row"] == 2 and body["needs_mapping"] is False
    assert body["mapping"] == {"date": 0, "debit": None, "credit": None, "amount": 2, "description": 1}
    st = body["stats"]
    assert (st["total"], st["valid"], st["errors"]) == (5, 4, 1)
    assert float(st["new_income"]) == 3_000_000 and float(st["new_expense"]) == 75_000
    assert st["from"] == "2026-03-05" and st["to"] == "2026-03-07"
    assert client.get("/api/transactions", headers=auth).json() == []  # la vista previa no guarda


def test_commit_creates_transactions_and_updates_balance(client, auth, bank):
    rows = preview(client, auth, bank).json()["rows"]
    r = client.post("/api/imports/commit", headers=auth, json={"account_id": bank["id"], "rows": to_commit(rows)})
    assert r.status_code == 201 and r.json() == {"created": 4, "skipped": 0}
    acc = client.get("/api/accounts", headers=auth).json()[0]
    assert float(acc["balance"]) == 1_000_000 + 3_000_000 - 50_000 - 25_000


def test_reimporting_same_file_flags_exact_duplicates_and_commit_skips_them(client, auth, bank):
    rows = preview(client, auth, bank).json()["rows"]
    client.post("/api/imports/commit", headers=auth, json={"account_id": bank["id"], "rows": to_commit(rows)})

    again = preview(client, auth, bank).json()
    assert again["stats"]["exact_duplicates"] == 4
    assert float(again["stats"]["new_expense"]) == 0
    r = client.post("/api/imports/commit", headers=auth, json={"account_id": bank["id"], "rows": to_commit(again["rows"])})
    assert r.json() == {"created": 0, "skipped": 4}
    assert len(client.get("/api/transactions", headers=auth).json()) == 4


def test_two_identical_lines_in_one_file_are_not_duplicates_of_each_other(client, auth, bank):
    rows = preview(client, auth, bank).json()["rows"]
    cruz = [r for r in rows if "Cruz" in r["description"]]
    assert len(cruz) == 2 and cruz[0]["import_hash"] != cruz[1]["import_hash"]
    assert all(r["duplicate"] is None for r in cruz)


def test_manual_entry_is_flagged_as_possible_duplicate(client, auth, bank):
    client.post("/api/transactions", headers=auth, json={
        "account_id": bank["id"], "kind": "expense", "amount": 50_000, "note": "mercado", "date": "2026-03-05"})
    rows = preview(client, auth, bank).json()
    assert rows["stats"]["possible_duplicates"] == 1
    exito = next(r for r in rows["rows"] if "EXITO" in r["description"])
    assert exito["duplicate"] == "possible"


def test_preview_suggests_categories_learned_before(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    client.post("/api/transactions", headers=auth, json={
        "account_id": bank["id"], "kind": "expense", "amount": 9_000, "note": "Éxito Calle 80",
        "category_id": mercado, "date": date.today().isoformat()})
    rows = preview(client, auth, bank).json()["rows"]
    exito = next(r for r in rows if "EXITO" in r["description"])
    assert exito["category_id"] == mercado
    assert next(r for r in rows if "NOMINA" in r["description"])["category_id"] is None


def test_commit_learns_categories_and_tags(client, auth, bank):
    rows = preview(client, auth, bank).json()["rows"]
    salud = category_id(client, auth, "Salud")
    payload = to_commit(rows)
    for p in payload:
        if "Cruz" in p["description"]:
            p["category_id"], p["tags"] = salud, ["farmacia"]
    client.post("/api/imports/commit", headers=auth, json={"account_id": bank["id"], "rows": payload})
    s = client.get("/api/categorize", headers=auth, params={"text": "Cruz Verde", "kind": "expense"}).json()["suggestion"]
    assert s["category_id"] == salud
    assert client.get("/api/transactions", headers=auth, params={"tag": "farmacia"}).headers["x-total-count"] == "2"


def test_credit_card_statement_with_invert_raises_debt(client, auth):
    card = client.post("/api/accounts", headers=auth, json={
        "name": "Visa", "type": "credit_card", "institution": "davivienda", "initial_balance": 0, "credit_limit": 3_000_000}).json()
    csv = "Fecha,Descripcion,Valor\n10/03/2026,Zara,200000\n11/03/2026,Pago tarjeta,-150000\n".encode()
    rows = preview(client, auth, card, csv, invert="true").json()["rows"]
    # en un extracto de tarjeta las compras vienen positivas: con «invert» son gasto y el pago es ingreso
    assert [(r["kind"], float(r["amount"])) for r in rows] == [("expense", 200_000.0), ("income", 150_000.0)]
    plain = preview(client, auth, card, csv).json()["rows"]
    assert plain[0]["kind"] == "income"  # sin invert se leería al revés
    client.post("/api/imports/commit", headers=auth, json={"account_id": card["id"], "rows": to_commit(rows)})
    assert float(client.get("/api/debts", headers=auth).json()[0]["current_balance"]) == 50_000


def test_debit_credit_columns_and_manual_mapping(client, auth, bank):
    csv = "Movimientos\nFecha;Detalle;Débito;Crédito\n01/04/2026;Retiro;200.000;\n02/04/2026;Abono;;1.500.000\n".encode("cp1252")
    body = preview(client, auth, bank, csv).json()
    assert [(r["kind"], float(r["amount"])) for r in body["rows"]] == [("expense", 200_000.0), ("income", 1_500_000.0)]

    raw = "01/04/2026,Cafe,4000\n02/04/2026,Taxi,9000\n".encode()  # sin encabezados
    needs = preview(client, auth, bank, raw).json()
    assert needs["needs_mapping"] is True and needs["columns"] == ["Columna 1", "Columna 2", "Columna 3"]
    ok = preview(client, auth, bank, raw, date_col="0", description_col="1", amount_col="2").json()
    assert ok["needs_mapping"] is False and len(ok["rows"]) == 2 and ok["rows"][0]["kind"] == "income"


def test_mdy_date_order(client, auth, bank):
    csv = "Date,Description,Amount\n03/05/2026,Coffee,-4\n".encode()
    assert preview(client, auth, bank, csv).json()["rows"][0]["date"] == "2026-05-03"          # dd/mm por defecto
    assert preview(client, auth, bank, csv, date_order="mdy").json()["rows"][0]["date"] == "2026-03-05"


def test_upload_validation_and_security(client, auth, bank):
    assert preview(client, auth, bank, b"%PDF-1.4", "extracto.pdf").status_code == 422
    assert preview(client, auth, bank, b"", "vacio.csv").status_code == 422
    assert client.post("/api/imports/preview", headers=auth, files={"file": ("a.csv", b"x", "text/csv")},
                       data={"account_id": "9999"}).status_code == 404
    assert client.post("/api/imports/preview", files={"file": ("a.csv", b"x", "text/csv")},
                       data={"account_id": "1"}).status_code == 401

    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    assert client.post("/api/imports/preview", headers=other, files={"file": ("a.csv", BANCOLOMBIA, "text/csv")},
                       data={"account_id": str(bank["id"])}).status_code == 404
    rows = preview(client, auth, bank).json()["rows"]
    assert client.post("/api/imports/commit", headers=other,
                       json={"account_id": bank["id"], "rows": to_commit(rows)}).status_code == 404


def test_commit_validates_rows(client, auth, bank):
    rows = to_commit(preview(client, auth, bank).json()["rows"])
    bad_cat = [{**rows[0], "category_id": 9999}]
    assert client.post("/api/imports/commit", headers=auth, json={"account_id": bank["id"], "rows": bad_cat}).status_code == 404
    bad_amount = [{**rows[0], "amount": -5}]
    assert client.post("/api/imports/commit", headers=auth, json={"account_id": bank["id"], "rows": bad_amount}).status_code == 422
    bad_hash = [{**rows[0], "import_hash": "zzz"}]
    assert client.post("/api/imports/commit", headers=auth, json={"account_id": bank["id"], "rows": bad_hash}).status_code == 422
    assert client.post("/api/imports/commit", headers=auth, json={"account_id": bank["id"], "rows": []}).status_code == 422
    same = [rows[0], rows[0]]  # la misma fila enviada dos veces solo se crea una vez
    assert client.post("/api/imports/commit", headers=auth, json={"account_id": bank["id"], "rows": same}).json() == {"created": 1, "skipped": 1}
