"""
Score value (SPEC §4.3). Code NEUF, aucun oracle. Property tests + conventions
documentées là où il n'y a pas d'autorité.

Conventions actées (pas d'oracle) :
- EV = mktcap + total_debt − cash (même définition partout).
- Numérateur = moyenne 5 ans (FCF_5y/EBIT_5y/NI_5y), JAMAIS TTM (Graham-Dodd).
- Numérateur NÉGATIF → yield négatif → z bas (légitimement peu attractif), PAS NaN.
- Sous-métrique INDÉFINIE (EV≤0, mktcap≤0, donnée manquante) → NaN, moyennée sur
  les sous-métriques disponibles (un NaN ne contamine pas tout value_xs_z).
- Historique < 5 ans → fail-neutral : pas de value score fabriqué (NaN), le nom
  garde son quality score mais sort du périmètre value.
- nonscore (FIN_STRUCTURE) → exclu du z value (NaN).
"""
import numpy as np
import pandas as pd

from qv.brain.value import compute_value, compute_yields, own_history_pctile

METRICS = ("fcf_ev", "ebit_ev", "e_p")
VAL = dict(shrinkage_lambda=0.5, winsor=(0.05, 0.95), min_years=5, metrics=METRICS)


def _df(rows):
    return pd.DataFrame(rows).set_index("tk")


# ── compute_yields (par nom) ──
def test_ev_definition_mktcap_plus_debt_minus_cash():
    df = _df([{"tk": "X", "fcf_5y": 10, "ebit_5y": 20, "ni_5y": 5,
               "mktcap": 100, "total_debt": 50, "cash": 10, "years_available": 5}])
    assert compute_yields(df, min_years=5).loc["X", "ev"] == 140.0


def test_yields_use_5y_numerator_over_current_denominator():
    df = _df([{"tk": "X", "fcf_5y": 10, "ebit_5y": 20, "ni_5y": 5,
               "mktcap": 100, "total_debt": 50, "cash": 10, "years_available": 5}])
    y = compute_yields(df, min_years=5)
    assert y.loc["X", "fcf_ev"] == 10 / 140
    assert y.loc["X", "ebit_ev"] == 20 / 140
    assert y.loc["X", "e_p"] == 5 / 100


def test_insufficient_history_yields_all_nan():
    df = _df([{"tk": "Y", "fcf_5y": 10, "ebit_5y": 20, "ni_5y": 5,
               "mktcap": 100, "total_debt": 50, "cash": 10, "years_available": 2}])
    y = compute_yields(df, min_years=5)
    assert y.loc["Y", ["fcf_ev", "ebit_ev", "e_p"]].isna().all()


def test_negative_numerator_is_negative_yield_not_nan():
    df = _df([{"tk": "N", "fcf_5y": -10, "ebit_5y": 20, "ni_5y": 5,
               "mktcap": 100, "total_debt": 50, "cash": 10, "years_available": 5}])
    fcf_ev = compute_yields(df, min_years=5).loc["N", "fcf_ev"]
    assert fcf_ev < 0 and np.isfinite(fcf_ev)


def test_negative_ev_kills_ev_yields_but_keeps_e_p():
    df = _df([{"tk": "Z", "fcf_5y": 10, "ebit_5y": 20, "ni_5y": 5,
               "mktcap": 100, "total_debt": 10, "cash": 200, "years_available": 5}])  # EV=-90
    y = compute_yields(df, min_years=5)
    assert np.isnan(y.loc["Z", "fcf_ev"]) and np.isnan(y.loc["Z", "ebit_ev"])
    assert y.loc["Z", "e_p"] == 5 / 100


# ── compute_value (cross-section) ──
def _universe():
    # 5 noms scorables même secteur, yields croissants ; +1 nonscore ; +1 historique court.
    rows = []
    for i, fcf in enumerate([1, 3, 5, 7, 9]):
        rows.append({"tk": f"T{i}", "sector": "Tech", "nonscore": False,
                     "fcf_5y": fcf, "ebit_5y": fcf * 2, "ni_5y": fcf,
                     "mktcap": 100, "total_debt": 0, "cash": 0, "years_available": 5})
    rows.append({"tk": "FIN", "sector": "Financials", "nonscore": True,
                 "fcf_5y": 8, "ebit_5y": 16, "ni_5y": 8,
                 "mktcap": 100, "total_debt": 0, "cash": 0, "years_available": 5})
    rows.append({"tk": "NEW", "sector": "Tech", "nonscore": False,
                 "fcf_5y": 9, "ebit_5y": 18, "ni_5y": 9,
                 "mktcap": 100, "total_debt": 0, "cash": 0, "years_available": 2})
    return _df(rows)


def test_cheaper_name_gets_higher_value_z():
    v = compute_value(_universe(), **VAL)["value_xs_z"]
    assert v["T0"] < v["T1"] < v["T2"] < v["T3"] < v["T4"]


def test_nonscore_excluded_from_value():
    v = compute_value(_universe(), **VAL)["value_xs_z"]
    assert np.isnan(v["FIN"])


def test_insufficient_history_excluded_from_value():
    v = compute_value(_universe(), **VAL)["value_xs_z"]
    assert np.isnan(v["NEW"])


def test_value_z_averages_over_available_submetrics():
    """Un nom EV<0 (fcf_ev/ebit_ev NaN) garde un value_xs_z fini via e_p seul."""
    uni = _universe()
    uni.loc["T2", ["total_debt", "cash"]] = [10, 200]  # EV = 100+10-200 = -90
    v = compute_value(uni, **VAL)["value_xs_z"]
    assert np.isfinite(v["T2"])


# ── own_history_pctile (GARDE-FOU) ──
def test_own_history_pctile_high_when_above_history():
    assert own_history_pctile(0.12, [0.04, 0.05, 0.06, 0.05]) == 1.0


def test_own_history_pctile_low_when_below_history():
    assert own_history_pctile(0.02, [0.04, 0.05, 0.06, 0.05]) == 0.0
