"""
Assemblage du pipeline (SPEC §4.6) : combined_z → drop NIVEAU détresse → gate →
equal_weight → caps → cash. Statut explicite par nom (auditabilité §8).
Caps volontairement non-mordants ici (testés à part) → on isole la mécanique.
"""
import numpy as np
import pandas as pd

from qv.brain.construct import build_portfolio

LEVEL = dict(interest_cov_min=2.0, net_debt_ebitda_max=3.5, fcf_ni_min=0.6, fcf_ni_max=2.0)
PIPE = dict(
    weight_quality=0.5, weight_value=0.5, gate_threshold=0.0,
    level_thresholds=LEVEL, position_cap=1.0, sector_cap=1.0, cash_buffer=0.15,
)


def _df(rows):
    return pd.DataFrame(rows).set_index("tk")


def _universe():
    return _df([
        # selected : scoré ≥ gate, niveau OK
        {"tk": "SEL", "sector": "A", "quality_z": 1.0, "value_xs_z": 0.5,
         "interest_coverage": 5.0, "net_debt_ebitda": 1.0, "fcf_ni": 1.0},
        # below_gate : combined_z < 0
        {"tk": "LOW", "sector": "A", "quality_z": -1.0, "value_xs_z": -1.0,
         "interest_coverage": 5.0, "net_debt_ebitda": 1.0, "fcf_ni": 1.0},
        # distress_excluded : combined_z ≥ gate mais couverture < 2
        {"tk": "DIS", "sector": "B", "quality_z": 1.0, "value_xs_z": 1.0,
         "interest_coverage": 1.0, "net_debt_ebitda": 1.0, "fcf_ni": 1.0},
        # out_of_perimeter : pas de combined_z (nonscore / historique court)
        {"tk": "OUT", "sector": "B", "quality_z": np.nan, "value_xs_z": np.nan,
         "interest_coverage": 5.0, "net_debt_ebitda": 1.0, "fcf_ni": 1.0},
    ])


def test_pipeline_assigns_explicit_status_per_name():
    p = build_portfolio(_universe(), sectors=_universe()["sector"], **PIPE)
    assert p.positions.loc["SEL", "status"] == "selected"
    assert p.positions.loc["LOW", "status"] == "below_gate"
    assert p.positions.loc["DIS", "status"] == "distress_excluded"
    assert p.positions.loc["OUT", "status"] == "out_of_perimeter"


def test_pipeline_only_selected_get_weight_rest_zero():
    uni = _universe()
    p = build_portfolio(uni, sectors=uni["sector"], **PIPE)
    assert p.positions.loc["SEL", "weight"] > 0
    assert (p.positions.loc[["LOW", "DIS", "OUT"], "weight"] == 0).all()


def test_pipeline_weights_plus_cash_sum_to_one():
    uni = _universe()
    p = build_portfolio(uni, sectors=uni["sector"], **PIPE)
    assert p.cash == 0.15
    assert p.positions["weight"].sum() + p.cash == 1.0


def test_pipeline_empty_selection_is_all_cash_no_crash():
    """Mauvais régime : tout rate le gate → 0 sélectionné → 100 % cash, pas de
    division par zéro (fail-neutral, comportement défensif propre)."""
    uni = _df([
        {"tk": "X", "sector": "A", "quality_z": -2.0, "value_xs_z": -2.0,
         "interest_coverage": 5.0, "net_debt_ebitda": 1.0, "fcf_ni": 1.0},
        {"tk": "Y", "sector": "A", "quality_z": -3.0, "value_xs_z": -1.0,
         "interest_coverage": 5.0, "net_debt_ebitda": 1.0, "fcf_ni": 1.0},
    ])
    p = build_portfolio(uni, sectors=uni["sector"], **PIPE)
    assert p.cash == 1.0
    assert (p.positions["weight"] == 0).all()
    assert (p.positions["status"] == "below_gate").all()


def test_pipeline_deterministic():
    uni = _universe()
    a = build_portfolio(uni, sectors=uni["sector"], **PIPE)
    b = build_portfolio(uni, sectors=uni["sector"], **PIPE)
    pd.testing.assert_frame_equal(a.positions, b.positions)
    assert a.cash == b.cash
