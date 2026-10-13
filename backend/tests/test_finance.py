import pytest

from app.services import finance


def test_ea_to_monthly():
    # 12 % EA ≈ 0.9489 % mensual
    assert finance.monthly_rate(12, "EA") == pytest.approx(0.009489, abs=1e-6)
    assert finance.monthly_rate(2, "MV") == pytest.approx(0.02)
    assert finance.monthly_rate(24, "NA") == pytest.approx(0.02)


def test_loan_payment_known_value():
    # 10 millones, 1 % mensual, 12 meses -> cuota ≈ 888.487,89
    assert finance.loan_payment(10_000_000, 0.01, 12) == pytest.approx(888_487.89, abs=0.01)


def test_amortize_pays_off_and_matches_term():
    r, n = 0.01, 12
    pay = finance.loan_payment(10_000_000, r, n)
    res = finance.amortize(10_000_000, r, pay)
    assert res["months"] == n
    assert res["rows"][-1]["balance"] == 0


def test_extra_payment_saves_interest():
    r, pay = 0.01, finance.loan_payment(10_000_000, 0.01, 36)
    base = finance.amortize(10_000_000, r, pay)
    fast = finance.amortize(10_000_000, r, pay, extra=200_000)
    assert fast["months"] < base["months"]
    assert fast["total_interest"] < base["total_interest"]


def test_payment_below_interest_raises():
    with pytest.raises(ValueError):
        finance.amortize(1_000_000, 0.02, 10_000)  # interés mensual = 20.000


def test_savings_required():
    # sin interés: 1.2M en 12 meses = 100k
    assert finance.savings_required(1_200_000, 0, 0, 12) == pytest.approx(100_000)
    # con interés se necesita menos
    assert finance.savings_required(1_200_000, 0, 0.01, 12) < 100_000
    # meta ya cubierta
    assert finance.savings_required(1_000, 5_000, 0.01, 12) == 0
