"""
Bouclier détresse (SPEC §4.4). Code NEUF, aucun oracle de parité.

Deux écrans STRICTEMENT séparés (le MC ne valide QUE le niveau) :
- level_pass : écran de NIVEAU (validé par MC) → exclusion dure du bucket value.
- trend_pass : écran de TENDANCE (advisory, NON validé, risque de circularité).

Fail-neutral conservateur : pour un bouclier, donnée manquante = on ne peut pas
confirmer la sûreté → FAIL (on n'accumule pas un nom dont on ne peut mesurer la
détresse). Jamais un faux ACCUMULER (SPEC §8).
"""
import numpy as np
import pandas as pd

from qv.brain.distress import level_pass, trend_pass

LEVEL = dict(interest_cov_min=2.0, net_debt_ebitda_max=3.5, fcf_ni_min=0.6, fcf_ni_max=2.0)
TREND = dict(margin_trend_min=-0.01, roic_trend_min=-0.01)


def _df(rows):
    return pd.DataFrame(rows).set_index("tk")


# ── NIVEAU ──
def test_clean_name_passes_level():
    df = _df([{"tk": "OK", "interest_coverage": 5.0, "net_debt_ebitda": 1.0, "fcf_ni": 1.0}])
    assert bool(level_pass(df, **LEVEL)["OK"]) is True


def test_low_interest_coverage_fails():
    df = _df([{"tk": "X", "interest_coverage": 1.5, "net_debt_ebitda": 1.0, "fcf_ni": 1.0}])
    assert bool(level_pass(df, **LEVEL)["X"]) is False


def test_high_leverage_fails():
    df = _df([{"tk": "X", "interest_coverage": 5.0, "net_debt_ebitda": 4.0, "fcf_ni": 1.0}])
    assert bool(level_pass(df, **LEVEL)["X"]) is False


def test_fcf_ni_out_of_band_fails_both_sides():
    low = _df([{"tk": "L", "interest_coverage": 5.0, "net_debt_ebitda": 1.0, "fcf_ni": 0.4}])
    high = _df([{"tk": "H", "interest_coverage": 5.0, "net_debt_ebitda": 1.0, "fcf_ni": 2.5}])
    assert bool(level_pass(low, **LEVEL)["L"]) is False
    assert bool(level_pass(high, **LEVEL)["H"]) is False


def test_missing_level_metric_fails_neutral():
    """Valeur manquante → FAIL (conservateur), jamais un faux ACCUMULER."""
    df = _df([{"tk": "N", "interest_coverage": np.nan, "net_debt_ebitda": 1.0, "fcf_ni": 1.0}])
    assert bool(level_pass(df, **LEVEL)["N"]) is False


def test_missing_level_column_fails_neutral():
    """Colonne absente (métrique non calculée) → FAIL (fail-neutral robuste)."""
    df = _df([{"tk": "N", "interest_coverage": 5.0, "net_debt_ebitda": 1.0}])  # pas de fcf_ni
    assert bool(level_pass(df, **LEVEL)["N"]) is False


# ── TENDANCE (advisory, séparée) ──
def test_flat_trend_passes():
    df = _df([{"tk": "F", "margin_trend": 0.0, "roic_trend": 0.0}])
    assert bool(trend_pass(df, **TREND)["F"]) is True


def test_declining_margin_fails_trend():
    df = _df([{"tk": "D", "margin_trend": -0.05, "roic_trend": 0.0}])
    assert bool(trend_pass(df, **TREND)["D"]) is False


def test_missing_trend_fails_neutral():
    df = _df([{"tk": "N", "margin_trend": np.nan, "roic_trend": 0.0}])
    assert bool(trend_pass(df, **TREND)["N"]) is False


def test_level_and_trend_are_independent():
    """Un nom peut passer le NIVEAU (validé) et rater la TENDANCE (non validée).
    Verrouille la séparation : le MC de niveau ne valide pas la tendance."""
    df = _df([{
        "tk": "D", "interest_coverage": 5.0, "net_debt_ebitda": 1.0, "fcf_ni": 1.0,
        "margin_trend": -0.05, "roic_trend": -0.05,
    }])
    assert bool(level_pass(df, **LEVEL)["D"]) is True
    assert bool(trend_pass(df, **TREND)["D"]) is False
