from datetime import date, timedelta

from app.clock import today as clock_today
from app.services.networth import _month_ends
from app.services.queries import prev_month

TODAY = clock_today()
THIS = TODAY.strftime("%Y-%m")
LAST = prev_month(THIS)
BEFORE = prev_month(LAST)


def first_of(month: str) -> str:
    return f"{month}-01"


def tx(client, auth, account, kind, amount, day):
    r = client.post("/api/transactions", headers=auth, json={"account_id": account["id"], "kind": kind, "amount": amount, "date": day})
    assert r.status_code == 201


def history(client, auth, months=12):
    r = client.get("/api/net-worth", headers=auth, params={"months": months})
    assert r.status_code == 200
    return r.json()


def worth(data):
    return {p["month"]: float(p["net_worth"]) for p in data["points"]}


def test_month_ends_helper():
    ends = _month_ends(date(2026, 1, 15), date(2026, 3, 10), 12)
    assert ends == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 10)]   # el mes en curso termina hoy
    assert len(_month_ends(date(2020, 1, 1), date(2026, 3, 10), 6)) == 6       # tope de meses
    assert _month_ends(date(2025, 12, 5), date(2026, 1, 5), 12)[0] == date(2025, 12, 31)  # cruza el año


def test_cash_is_rebuilt_exactly_month_by_month(client, auth, bank):
    tx(client, auth, bank, "income", 500_000, first_of(BEFORE))
    tx(client, auth, bank, "expense", 200_000, first_of(LAST))
    data = history(client, auth)
    assert worth(data) == {BEFORE: 1_500_000.0, LAST: 1_300_000.0, THIS: 1_300_000.0}
    assert float(data["change"]) == -200_000          # de 1.500.000 (primer mes) a 1.300.000 (hoy)
    assert [p["estimated"] for p in data["points"]] == [True, True, False]    # el mes en curso no es estimado


def test_card_debt_is_undone_from_today(client, auth, bank):
    card = client.post("/api/accounts", headers=auth, json={"name": "Visa", "type": "credit_card", "institution": "bbva",
                                                            "initial_balance": 800_000, "credit_limit": 5_000_000}).json()
    tx(client, auth, card, "expense", 100_000, first_of(THIS))      # compra de este mes: la deuda sube a 900k
    tx(client, auth, bank, "income", 1, first_of(LAST))             # para que la historia empiece el mes pasado
    data = {p["month"]: p for p in history(client, auth)["points"]}
    assert float(data[THIS]["debt"]) == 900_000
    assert float(data[LAST]["debt"]) == 800_000                      # antes de la compra debía 800k
    assert float(data[THIS]["net_worth"]) == 1_000_001 - 900_000
    assert float(data[LAST]["net_worth"]) == 1_000_001 - 800_000


def test_debt_payments_are_undone_too(client, auth, bank):
    debt = client.post("/api/debts", headers=auth, json={"name": "Moto", "kind": "loan", "original_amount": 1_000_000,
                                                         "current_balance": 1_000_000, "rate": 0, "term_months": 10}).json()
    tx(client, auth, bank, "income", 1, first_of(LAST))
    client.post(f"/api/debts/{debt['id']}/payments", headers=auth, json={"amount": 100_000, "date": first_of(THIS)})
    data = {p["month"]: float(p["debt"]) for p in history(client, auth)["points"]}
    assert data[THIS] == 900_000 and data[LAST] == 1_000_000           # el pago de este mes no existía el mes pasado


def test_empty_user_and_history_starts_at_first_movement(client, auth):
    data = history(client, auth)
    assert data["months"] == 1 and float(data["points"][0]["net_worth"]) == 0 and data["change"] == 0
    acc = client.post("/api/accounts", headers=auth, json={"name": "A", "type": "cash", "initial_balance": 100}).json()
    tx(client, auth, acc, "income", 50, first_of(LAST))
    assert len(history(client, auth)["points"]) == 2                    # no inventa meses anteriores al primer movimiento
    assert len(history(client, auth, months=2)["points"]) == 2


def test_months_limit_validation_and_privacy(client, auth, bank):
    tx(client, auth, bank, "income", 1, (TODAY - timedelta(days=400)).isoformat())
    assert len(history(client, auth, months=6)["points"]) == 6
    assert client.get("/api/net-worth", headers=auth, params={"months": 1}).status_code == 422
    assert client.get("/api/net-worth", headers=auth, params={"months": 37}).status_code == 422
    assert client.get("/api/net-worth").status_code == 401
    client.post("/api/auth/register", json={"email": "o@o.co", "password": "12345678", "name": "Otro"})
    tok = client.post("/api/auth/login", data={"username": "o@o.co", "password": "12345678"}).json()["access_token"]
    assert float(history(client, {"Authorization": f"Bearer {tok}"})["points"][-1]["net_worth"]) == 0
