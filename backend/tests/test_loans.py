from datetime import date, timedelta
from decimal import Decimal

from conftest import category_id

TODAY = date.today().isoformat()


def new_loan(client, auth, **extra):
    body = {"person": "Camilo", "direction": "lent", "amount": 100_000, "date": TODAY, **extra}
    r = client.post("/api/loans", headers=auth, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def balance(client, auth, name="Ahorros"):
    return float(next(a for a in client.get("/api/accounts", headers=auth).json() if a["name"] == name)["balance"])


def month_summary(client, auth):
    return client.get(f"/api/summary?month={date.today():%Y-%m}", headers=auth).json()


def test_lending_with_account_moves_balance_but_is_not_an_expense(client, auth, bank):
    loan = new_loan(client, auth, account_id=bank["id"], amount=200_000)
    assert balance(client, auth) == 800_000
    s = month_summary(client, auth)
    assert float(s["expense"]) == 0 and float(s["income"]) == 0
    assert float(loan["outstanding"]) == 200_000 and loan["settled"] is False

    r = client.post(f"/api/loans/{loan['id']}/payments", headers=auth,
                    json={"amount": 50_000, "date": TODAY, "account_id": bank["id"]})
    assert r.status_code == 201 and float(r.json()["outstanding"]) == 150_000
    assert balance(client, auth) == 850_000
    assert float(month_summary(client, auth)["income"]) == 0  # cobrar tampoco es un ingreso


def test_loan_without_account_only_tracks_the_debt(client, auth, bank):
    loan = new_loan(client, auth)
    assert balance(client, auth) == 1_000_000
    client.post(f"/api/loans/{loan['id']}/payments", headers=auth, json={"amount": 100_000, "date": TODAY})
    got = client.get(f"/api/loans/{loan['id']}", headers=auth).json()
    assert got["settled"] is True and float(got["outstanding"]) == 0
    assert client.get("/api/loans", headers=auth).json() == []                      # solo abiertos por defecto
    assert len(client.get("/api/loans", headers=auth, params={"status": "settled"}).json()) == 1


def test_borrowed_money_flows_the_other_way(client, auth, bank):
    loan = new_loan(client, auth, direction="borrowed", amount=300_000, account_id=bank["id"], person="Mamá")
    assert balance(client, auth) == 1_300_000
    client.post(f"/api/loans/{loan['id']}/payments", headers=auth,
                json={"amount": 100_000, "date": TODAY, "account_id": bank["id"]})
    assert balance(client, auth) == 1_200_000
    s = client.get("/api/loans/summary", headers=auth).json()
    assert float(s["i_owe"]) == 200_000 and float(s["owed_to_me"]) == 0 and float(s["net"]) == -200_000


def test_cannot_overpay_and_payment_validation(client, auth, bank):
    loan = new_loan(client, auth, amount=1_000)
    url = f"/api/loans/{loan['id']}/payments"
    assert client.post(url, headers=auth, json={"amount": 1_001, "date": TODAY}).status_code == 422
    assert client.post(url, headers=auth, json={"amount": 0, "date": TODAY}).status_code == 422
    assert client.post(url, headers=auth, json={"amount": 5, "date": TODAY, "account_id": 999}).status_code == 404
    assert client.post("/api/loans", headers=auth, json={"person": " ", "direction": "lent", "amount": 5, "date": TODAY}).status_code == 422
    late = (date.today() - timedelta(days=1)).isoformat()
    assert client.post("/api/loans", headers=auth, json={"person": "X", "direction": "lent", "amount": 5, "date": TODAY, "due_date": late}).status_code == 422


def test_delete_payment_and_loan_revert_balances(client, auth, bank):
    loan = new_loan(client, auth, account_id=bank["id"], amount=200_000)
    paid = client.post(f"/api/loans/{loan['id']}/payments", headers=auth,
                       json={"amount": 80_000, "date": TODAY, "account_id": bank["id"]}).json()
    assert balance(client, auth) == 880_000
    after = client.delete(f"/api/loans/{loan['id']}/payments/{paid['payments'][0]['id']}", headers=auth).json()
    assert float(after["outstanding"]) == 200_000 and balance(client, auth) == 800_000
    assert client.delete(f"/api/loans/{loan['id']}", headers=auth).status_code == 204
    assert balance(client, auth) == 1_000_000 and client.get("/api/loans", headers=auth, params={"status": "all"}).json() == []


def test_loan_transactions_cannot_be_edited_or_deleted_directly(client, auth, bank):
    new_loan(client, auth, account_id=bank["id"])
    tx = client.get("/api/transactions", headers=auth).json()[0]
    assert tx["loan_id"] is not None
    assert client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"amount": 1}).status_code == 422
    assert client.delete(f"/api/transactions/{tx['id']}", headers=auth).status_code == 422


def test_split_equally_only_my_share_is_expense(client, auth, bank):
    comida = category_id(client, auth, "Ocio")
    r = client.post("/api/splits", headers=auth, json={
        "account_id": bank["id"], "category_id": comida, "total": 120_000, "date": TODAY, "note": "Cena",
        "participants": [{"person": "Ana"}, {"person": "Luis"}, {"person": "Pedro"}]})
    assert r.status_code == 201
    body = r.json()
    assert float(body["my_share"]) == 30_000 and [float(l["amount"]) for l in body["loans"]] == [30_000.0] * 3
    assert balance(client, auth) == 1_000_000 - 120_000                       # pagaste todo
    s = month_summary(client, auth)
    assert float(s["expense"]) == 30_000 and s["expense_by_category"][0]["category"] == "Ocio"  # pero gastaste 30k
    summary = client.get("/api/loans/summary", headers=auth).json()
    assert float(summary["owed_to_me"]) == 90_000 and len(summary["people"]) == 3


def test_split_equal_rounding_goes_to_me(client, auth, bank):
    r = client.post("/api/splits", headers=auth, json={
        "account_id": bank["id"], "total": 100_000, "date": TODAY, "participants": [{"person": "A"}, {"person": "B"}]}).json()
    assert [Decimal(str(l["amount"])) for l in r["loans"]] == [Decimal("33333.33")] * 2
    assert Decimal(str(r["my_share"])) == Decimal("33333.34")


def test_split_with_custom_amounts_and_validation(client, auth, bank):
    ok = client.post("/api/splits", headers=auth, json={
        "account_id": bank["id"], "total": 100_000, "date": TODAY,
        "participants": [{"person": "A", "amount": 70_000}, {"person": "B", "amount": 30_000}]}).json()
    assert float(ok["my_share"]) == 0
    assert [t["note"] for t in client.get("/api/transactions", headers=auth).json() if "mi parte" in t["note"]] == []

    base = {"account_id": bank["id"], "total": 100_000, "date": TODAY}
    assert client.post("/api/splits", headers=auth, json={**base, "participants": [{"person": "A", "amount": 90_000}, {"person": "B", "amount": 20_000}]}).status_code == 422
    assert client.post("/api/splits", headers=auth, json={**base, "participants": [{"person": "A", "amount": 10}, {"person": "B"}]}).status_code == 422
    assert client.post("/api/splits", headers=auth, json={**base, "participants": []}).status_code == 422
    assert client.post("/api/splits", headers=auth, json={**base, "account_id": 999, "participants": [{"person": "A"}]}).status_code == 404


def test_split_on_credit_card_raises_the_debt_by_the_total(client, auth):
    card = client.post("/api/accounts", headers=auth, json={
        "name": "Visa", "type": "credit_card", "institution": "davivienda", "initial_balance": 0, "credit_limit": 2_000_000}).json()
    client.post("/api/splits", headers=auth, json={"account_id": card["id"], "total": 80_000, "date": TODAY,
                                                    "participants": [{"person": "A"}]})
    assert float(client.get("/api/debts", headers=auth).json()[0]["current_balance"]) == 80_000


def test_summary_nets_per_person_case_insensitively(client, auth, bank):
    new_loan(client, auth, person="Ana", amount=100_000)
    new_loan(client, auth, person="ana ", amount=50_000)
    new_loan(client, auth, person="Ana", direction="borrowed", amount=30_000)
    s = client.get("/api/loans/summary", headers=auth).json()
    assert len(s["people"]) == 1 and float(s["people"][0]["net"]) == 120_000
    assert float(s["owed_to_me"]) == 150_000 and float(s["i_owe"]) == 30_000


def test_deleting_account_with_loans_works_with_foreign_keys(client, auth, bank):
    loan = new_loan(client, auth, account_id=bank["id"])
    client.post(f"/api/loans/{loan['id']}/payments", headers=auth, json={"amount": 10, "date": TODAY, "account_id": bank["id"]})
    assert client.delete(f"/api/accounts/{bank['id']}", headers=auth).status_code == 204
    still = client.get(f"/api/loans/{loan['id']}", headers=auth).json()
    assert float(still["paid"]) == 10  # el registro del préstamo se conserva


def test_loan_due_alerts(client, auth, bank):
    soon = (date.today() + timedelta(days=2)).isoformat()
    late = (date.today() - timedelta(days=5)).isoformat()
    new_loan(client, auth, person="Ana", due_date=soon)
    old = client.post("/api/loans", headers=auth, json={"person": "Beto", "direction": "borrowed", "amount": 70_000,
                                                          "date": (date.today() - timedelta(days=30)).isoformat(), "due_date": late}).json()
    r = client.post("/api/notifications/refresh", headers=auth).json()
    titles = " | ".join(i["title"] for i in r["items"])
    assert r["new"] == 2 and "Beto" in titles and "Ana" in titles
    assert client.post("/api/notifications/refresh", headers=auth).json()["new"] == 0
    assert any("Le debes" in i["body"] for i in r["items"]) and any("te debe" in i["body"] for i in r["items"])
    client.post(f"/api/loans/{old['id']}/payments", headers=auth, json={"amount": 70_000, "date": TODAY})


def test_loans_are_private(client, auth, bank):
    loan = new_loan(client, auth)
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    other = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/loans", headers=other).json() == []
    assert client.get(f"/api/loans/{loan['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/loans/{loan['id']}", headers=other).status_code == 404
    assert client.post(f"/api/loans/{loan['id']}/payments", headers=other, json={"amount": 1, "date": TODAY}).status_code == 404
