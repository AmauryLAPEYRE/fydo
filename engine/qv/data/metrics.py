"""
Dérivation des fondamentaux FMP brut → contrat consommé par le cerveau.
Pure, déterministe, fail-neutral (champ manquant → NaN, jamais un crash).

Conventions (FMP, pas l'oracle yfinance — documentées) :
- ROIC : NOPAT / Invested Capital, avec
    NOPAT = EBIT × (1 − taux d'impôt effectif),  taux = incomeTaxExpense/incomeBeforeTax
    IC    = totalDebt + totalStockholdersEquity + minorityInterest − cashAndCashEquivalents
    (cash-netté, cohérent avec EV ; FMP ne fournit pas l'IC en line item → on tranche).
- Numérateurs value : moyennes 5 ans (FCF/EBIT/NI), pas TTM (Graham-Dodd).
- Métriques de détresse : dernier exercice (niveau courant).
- interestExpense ≤ 0 (pas de coût de dette) → couverture = +∞ (boîte sûre).
- Statements alignés par fiscalYear (newest-first) ; on n'utilise que les exercices
  communs aux trois états.
"""
from __future__ import annotations

import numpy as np


def _f(x):
    """Vers float, None → NaN."""
    return np.nan if x is None else float(x)


def _safe_div(a, b):
    a, b = _f(a), _f(b)
    if np.isnan(a) or np.isnan(b) or b == 0:
        return np.nan
    return a / b


def _mean(values):
    arr = np.array([_f(v) for v in values], dtype=float)
    return np.nan if arr.size == 0 or np.all(np.isnan(arr)) else float(np.nanmean(arr))


def _slope_per_year(values_newest_first):
    """Pente par an (chronologique). NaN si < 2 points valides."""
    v = np.array([_f(x) for x in values_newest_first], dtype=float)[::-1]
    mask = ~np.isnan(v)
    if mask.sum() < 2:
        return np.nan
    return float(np.polyfit(np.arange(len(v))[mask], v[mask], 1)[0])


def _tax_rate(income_row, default, lo, hi):
    tax = income_row.get("incomeTaxExpense")
    pretax = income_row.get("incomeBeforeTax")
    if tax is None or not pretax:  # pretax None/0
        return default
    r = tax / pretax
    return r if lo <= r <= hi else default


def _is_fin_structure(industry, keywords) -> bool:
    ind = (industry or "").lower()
    return any(k.lower() in ind for k in keywords)


def derive_fundamentals(responses, *, fin_structure_keywords, tax_default, tax_min, tax_max) -> dict:
    """FMP {profile, income, balance, cashflow, quote} → dict du contrat cerveau."""
    profile = responses["profile"][0]
    quote = responses["quote"][0]

    income = {r["fiscalYear"]: r for r in responses["income"]}
    balance = {r["fiscalYear"]: r for r in responses["balance"]}
    cashflow = {r["fiscalYear"]: r for r in responses["cashflow"]}
    years = sorted(set(income) & set(balance) & set(cashflow), reverse=True)
    inc = [income[y] for y in years]
    bal = [balance[y] for y in years]
    cf = [cashflow[y] for y in years]
    n = len(years)

    revenue = [r.get("revenue") for r in inc]
    gross_margin = [_safe_div(r.get("grossProfit"), r.get("revenue")) for r in inc]
    net_margin = [_safe_div(r.get("netIncome"), r.get("revenue")) for r in inc]

    roic = []
    for i, b in zip(inc, bal):
        nopat = _f(i.get("ebit")) * (1 - _tax_rate(i, tax_default, tax_min, tax_max))
        ic = (_f(b.get("totalDebt")) + _f(b.get("totalStockholdersEquity"))
              + _f(b.get("minorityInterest") or 0.0) - _f(b.get("cashAndCashEquivalents")))
        roic.append(_safe_div(nopat, ic))

    rev_cagr = np.nan
    if n > 1 and revenue[-1] not in (None, 0) and _f(revenue[-1]) > 0 and revenue[0] is not None:
        rev_cagr = (_f(revenue[0]) / _f(revenue[-1])) ** (1 / (n - 1)) - 1

    b0, i0, c0 = bal[0], inc[0], cf[0]
    interest = i0.get("interestExpense")
    interest_coverage = np.inf if (interest is None or _f(interest) <= 0) \
        else _safe_div(i0.get("ebit"), interest)
    net_debt = i0.get("netDebt", b0.get("netDebt"))
    if net_debt is None:
        net_debt = _f(b0.get("totalDebt")) - _f(b0.get("cashAndCashEquivalents"))

    return {
        "sector": profile.get("sector"),
        "nonscore": _is_fin_structure(profile.get("industry"), fin_structure_keywords),
        "currency": profile.get("currency"),
        "mktcap": quote.get("marketCap"),
        "roic_5y_avg": _mean(roic),
        "gross_margin_5y_avg": _mean(gross_margin),
        "net_margin_5y_avg": _mean(net_margin),
        "rev_cagr_5y": rev_cagr,
        "debt_to_equity": _safe_div(b0.get("totalDebt"), b0.get("totalStockholdersEquity")),
        "interest_coverage": interest_coverage,
        "net_debt_ebitda": _safe_div(net_debt, i0.get("ebitda")),
        "fcf_ni": _safe_div(c0.get("freeCashFlow"), i0.get("netIncome")),
        "margin_trend": _slope_per_year(gross_margin),
        "roic_trend": _slope_per_year(roic),
        "fcf_5y": _mean([r.get("freeCashFlow") for r in cf]),
        "ebit_5y": _mean([r.get("ebit") for r in inc]),
        "ni_5y": _mean([r.get("netIncome") for r in inc]),
        "total_debt": _f(b0.get("totalDebt")),
        "cash": _f(b0.get("cashAndCashEquivalents")),
        "years_available": n,
    }
