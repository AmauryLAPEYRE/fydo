"""
Dérivation FMP brut → contrat cerveau (qv/data/metrics.py). Code NEUF.
Testé contre une fixture FMP RÉELLE (AAPL) : on recalcule l'attendu depuis les
line items bruts et on vérifie que le mapping applique la bonne formule au bon
champ — pas des nombres magiques en dur.
"""
import json
import pathlib

import numpy as np
import pytest

from qv.data.metrics import derive_fundamentals

FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "fmp_sample_AAPL.json"
CONV = dict(fin_structure_keywords=("Bank", "Insurance"),
            tax_default=0.25, tax_min=0.0, tax_max=0.6)


@pytest.fixture
def aapl():
    return json.loads(FIX.read_text(encoding="utf-8"))


def _tax(r):
    t = r["incomeTaxExpense"] / r["incomeBeforeTax"]
    return t if 0.0 <= t <= 0.6 else 0.25


def test_identity_fields(aapl):
    out = derive_fundamentals(aapl, **CONV)
    assert out["sector"] == "Technology"
    assert out["nonscore"] is False          # Consumer Electronics ≠ banque/assureur
    assert out["currency"] == "USD"
    assert out["mktcap"] == aapl["quote"][0]["marketCap"]   # quote = capi fraîche
    assert out["years_available"] == 5


def test_margins_and_growth_from_raw(aapl):
    out = derive_fundamentals(aapl, **CONV)
    inc = aapl["income"]  # newest-first
    gm = np.mean([r["grossProfit"] / r["revenue"] for r in inc])
    nm = np.mean([r["netIncome"] / r["revenue"] for r in inc])
    rev = [r["revenue"] for r in inc]
    assert out["gross_margin_5y_avg"] == pytest.approx(gm)
    assert out["net_margin_5y_avg"] == pytest.approx(nm)
    assert out["rev_cagr_5y"] == pytest.approx((rev[0] / rev[-1]) ** (1 / 4) - 1)


def test_roic_uses_cash_netted_invested_capital(aapl):
    out = derive_fundamentals(aapl, **CONV)
    inc, bal = aapl["income"], aapl["balance"]
    roics = []
    for ii, bb in zip(inc, bal):
        nopat = ii["ebit"] * (1 - _tax(ii))
        ic = (bb["totalDebt"] + bb["totalStockholdersEquity"]
              + (bb["minorityInterest"] or 0.0) - bb["cashAndCashEquivalents"])
        roics.append(nopat / ic)
    assert out["roic_5y_avg"] == pytest.approx(np.mean(roics))


def test_distress_inputs_from_latest(aapl):
    out = derive_fundamentals(aapl, **CONV)
    b0, i0, c0 = aapl["balance"][0], aapl["income"][0], aapl["cashflow"][0]
    # interestExpense = 0 → couverture infinie (boîte sans coût de dette = sûre)
    assert out["interest_coverage"] == np.inf
    assert out["net_debt_ebitda"] == pytest.approx(b0["netDebt"] / i0["ebitda"])
    assert out["fcf_ni"] == pytest.approx(c0["freeCashFlow"] / i0["netIncome"])
    assert out["debt_to_equity"] == pytest.approx(b0["totalDebt"] / b0["totalStockholdersEquity"])


def test_value_numerators_are_5y_means(aapl):
    out = derive_fundamentals(aapl, **CONV)
    assert out["fcf_5y"] == pytest.approx(np.mean([r["freeCashFlow"] for r in aapl["cashflow"]]))
    assert out["ebit_5y"] == pytest.approx(np.mean([r["ebit"] for r in aapl["income"]]))
    assert out["ni_5y"] == pytest.approx(np.mean([r["netIncome"] for r in aapl["income"]]))


# ── robustesse / fail-neutral (réponses synthétiques minimales) ──
def _synthetic(industry="Software", years=2, revenue=100.0, interest=5.0):
    inc = [{"fiscalYear": str(2025 - k), "revenue": revenue, "grossProfit": 40.0,
            "ebit": 20.0, "ebitda": 25.0, "netIncome": 10.0, "incomeBeforeTax": 15.0,
            "incomeTaxExpense": 3.0, "interestExpense": interest} for k in range(years)]
    bal = [{"fiscalYear": str(2025 - k), "totalDebt": 50.0, "totalStockholdersEquity": 80.0,
            "minorityInterest": 0.0, "cashAndCashEquivalents": 10.0, "netDebt": 40.0,
            "ebitda": 25.0} for k in range(years)]
    cf = [{"fiscalYear": str(2025 - k), "freeCashFlow": 8.0, "netIncome": 10.0}
          for k in range(years)]
    return {"profile": [{"sector": "Technology", "industry": industry,
                         "currency": "USD", "marketCap": 1000.0}],
            "income": inc, "balance": bal, "cashflow": cf,
            "quote": [{"marketCap": 1000.0, "price": 10.0}]}


def test_fin_structure_flagged_by_industry():
    out = derive_fundamentals(_synthetic(industry="Banks - Diversified"), **CONV)
    assert out["nonscore"] is True


def test_short_history_reports_years_available():
    out = derive_fundamentals(_synthetic(years=2), **CONV)
    assert out["years_available"] == 2


def test_finite_interest_coverage_when_interest_positive():
    out = derive_fundamentals(_synthetic(interest=5.0), **CONV)
    assert out["interest_coverage"] == pytest.approx(20.0 / 5.0)


def test_missing_field_is_nan_not_crash():
    resp = _synthetic()
    resp["income"][0]["revenue"] = None          # marge du dernier exercice indéfinie
    out = derive_fundamentals(resp, **CONV)
    assert np.isfinite(out["gross_margin_5y_avg"])  # moyenné sur l'autre année dispo
