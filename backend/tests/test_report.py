import io
from datetime import date, timedelta

from pypdf import PdfReader

from app.services.queries import prev_month
from app.services.report import month_label
from conftest import category_id

TODAY = date.today()
MONTH = TODAY.strftime("%Y-%m")


def add(client, auth, account, amount, note="", kind="expense", day=None, category=None):
    r = client.post("/api/transactions", headers=auth, json={
        "account_id": account["id"], "category_id": category, "kind": kind, "amount": amount, "note": note,
        "date": (day or TODAY).isoformat()})
    assert r.status_code == 201


def report(client, auth, **params):
    return client.get("/api/reports/monthly", headers=auth, params=params)


def text_of(response) -> str:
    reader = PdfReader(io.BytesIO(response.content))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_month_label_in_spanish():
    assert month_label("2026-10") == "Octubre de 2026" and month_label("2026-01") == "Enero de 2026"


def test_report_is_a_real_pdf_with_the_key_numbers(client, auth, bank):
    mercado = category_id(client, auth, "Mercado")
    client.put(f"/api/budgets/{mercado}", headers=auth, json={"amount": 100_000})
    add(client, auth, bank, 3_000_000, "Nómina", kind="income")
    add(client, auth, bank, 150_000, "Éxito grande", category=mercado)
    add(client, auth, bank, 40_000, "Taxi")

    r = report(client, auth)
    assert r.status_code == 200 and r.content.startswith(b"%PDF-")
    assert r.headers["content-type"] == "application/pdf" and f"informe-{MONTH}.pdf" in r.headers["content-disposition"]
    text = text_of(r)
    assert f"Informe de {month_label(MONTH)}" in text
    assert "$3.000.000" in text and "$190.000" in text            # ingresos y gastos del mes
    assert "Mercado" in text and "150%" in text                    # 150.000 de un presupuesto de 100.000
    assert "Éxito grande" in text and "Sin categoría" in text
    assert "$2.810.000" in text                                    # balance del mes
    assert "Patrimonio neto" in text and "Cuenta de ahorros" in text and "savings" not in text  # en español
    assert len(PdfReader(io.BytesIO(r.content)).pages) == 1        # un informe corto cabe en una hoja


def test_report_compares_with_previous_month(client, auth, bank):
    last = date.fromisoformat(prev_month(MONTH) + "-10")
    add(client, auth, bank, 100_000, "Mes pasado", day=last)
    add(client, auth, bank, 150_000, "Este mes")
    assert "Gastos +50%" in text_of(report(client, auth))


def test_empty_month_still_produces_a_pdf(client, auth):
    r = report(client, auth, month="2020-01")
    assert r.status_code == 200 and "No hay gastos registrados" in text_of(r) and "Enero de 2020" in text_of(r)


def test_report_ignores_transfers_and_loans(client, auth, bank):
    other = client.post("/api/accounts", headers=auth, json={"name": "Nequi", "type": "wallet", "institution": "nequi", "initial_balance": 0}).json()
    client.post("/api/transfers", headers=auth, json={"from_account_id": bank["id"], "to_account_id": other["id"], "amount": 777_000, "date": TODAY.isoformat()})
    client.post("/api/loans", headers=auth, json={"person": "Ana", "direction": "lent", "amount": 555_000, "date": TODAY.isoformat(), "account_id": bank["id"]})
    add(client, auth, bank, 10_000, "real")
    text = text_of(report(client, auth))
    month_part = text.split("Cuentas y patrimonio")[0]  # lo que cuenta como ingreso/gasto del mes
    assert "$777.000" not in month_part and "$555.000" not in month_part
    assert "No hay gastos" not in text and "$10.000" in month_part
    assert "Te deben $555.000" in text.replace("\n", " ")   # los préstamos salen aparte, como pendientes
    assert "$777.000" in text                                 # y la transferencia sí movió el saldo de Nequi


def test_bold_markup_is_rendered_not_printed(client, auth, bank):
    add(client, auth, bank, 10_000, "x")
    text = text_of(report(client, auth))
    assert "Patrimonio neto" in text and "<b>" not in text and "</b>" not in text


def test_hostile_text_cannot_break_the_pdf(client, auth, bank):
    add(client, auth, bank, 5_000, "<b>negrita</b> & <unclosed <para>")
    add(client, auth, bank, 6_000, "</para><font size=999>")
    r = report(client, auth)
    assert r.status_code == 200 and r.content.startswith(b"%PDF-")
    assert "<b>negrita</b>" in text_of(r)  # se muestra tal cual, no se interpreta como marcado


def test_report_validation_and_privacy(client, auth, bank):
    add(client, auth, bank, 1_234, "secreto-del-usuario-uno")
    assert report(client, auth, month="2026-13").status_code == 422
    assert report(client, auth, month="hoy").status_code == 422
    assert client.get("/api/reports/monthly").status_code == 401
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = client.get("/api/reports/monthly", headers={"Authorization": f"Bearer {tok}"})
    assert "secreto-del-usuario-uno" not in text_of(other) and "No hay gastos" in text_of(other)


def test_report_with_card_and_many_categories(client, auth, bank):
    client.post("/api/accounts", headers=auth, json={"name": "Visa", "type": "credit_card", "institution": "bbva",
                                                     "initial_balance": 800_000, "credit_limit": 3_000_000})
    for i in range(12):  # más categorías que colores en la torta
        c = client.post("/api/categories", headers=auth, json={"name": f"Cat{i}", "kind": "expense"}).json()
        add(client, auth, bank, 1_000 * (i + 1), f"gasto {i}", category=c["id"])
    text = text_of(report(client, auth))
    assert "Tarjeta de crédito" in text and "-$800.000" in text and "Cat11" in text


def test_dozens_of_categories_are_grouped_instead_of_crashing(client, auth, bank):
    for i in range(60):
        c = client.post("/api/categories", headers=auth, json={"name": f"Categoría número {i}", "kind": "expense"}).json()
        add(client, auth, bank, 100 + i, f"movimiento {i}", category=c["id"])
    r = report(client, auth)
    assert r.status_code == 200
    text = text_of(r)
    assert "Otras (49 categorías)" in text and "Categoría número 59" in text   # la mayor se ve; las chicas se agrupan
    assert "Categoría número 0\n" not in text


def test_long_report_paginates(client, auth, bank):
    for i in range(70):
        client.post("/api/accounts", headers=auth, json={"name": f"Cuenta {i}", "type": "cash", "initial_balance": 1000 + i})
    r = report(client, auth)
    assert r.status_code == 200 and len(PdfReader(io.BytesIO(r.content)).pages) >= 2
