"""
Construction — gated equal-weight de base + plafonds (SPEC §4.6/§4.7).
Parité contre les sorties RÉELLES de l'oracle (gate, base, caps). Le TILT est EXCLU :
w_cg_last ne sert que de vecteur d'entrée arbitraire au test de l'algo de plafonds.
"""
import pathlib

import numpy as np
import pandas as pd
import pytest

from qv.brain.construct import apply_caps, equal_weight, gate_mask

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "oracle_golden_construct.pkl"


@pytest.fixture
def golden():
    return pd.read_pickle(FIXTURE)


def test_equal_weight_matches_oracle_base(golden):
    """equal_weight(gate) reproduit le `base` (gated equal-weight) de l'oracle."""
    got = equal_weight(golden["gate"])
    np.testing.assert_allclose(
        got.to_numpy(), golden["base"].to_numpy(), atol=1e-12
    )


def test_caps_match_oracle(golden):
    """apply_caps reproduit au point près les poids capés de l'oracle (algo de
    plafonds = trou de spec → convention oracle → parité)."""
    got = apply_caps(
        golden["w_cg_last"], golden["sectors"],
        position_cap=0.08, sector_cap=0.30, iterations=8,
    )
    np.testing.assert_allclose(
        got.to_numpy(), golden["w_capped_last"].to_numpy(), atol=1e-12
    )


def test_gate_mask_selects_at_or_above_threshold():
    score = pd.Series({"a": -0.5, "b": 0.0, "c": 0.3, "d": 1.2})
    mask = gate_mask(score, 0.0)
    assert mask.to_dict() == {"a": False, "b": True, "c": True, "d": True}


def test_equal_weight_sums_to_one_over_gated_only():
    mask = pd.Series({"a": True, "b": False, "c": True, "d": True})
    w = equal_weight(mask)
    assert w.sum() == pytest.approx(1.0)
    assert w["b"] == 0.0
    assert w["a"] == pytest.approx(1 / 3)


def test_caps_reduce_concentration_when_binding():
    """Vecteur concentré → les plafonds réduisent la ligne max ET le secteur max,
    et la somme reste 1. (L'algo itératif de l'oracle ne garantit pas ≤ cap exact ;
    la propriété honnête est : il dé-concentre.)"""
    w = pd.Series([0.50, 0.20, 0.15, 0.10, 0.05], index=list("ABCDE"))
    sectors = pd.Series(["S1", "S1", "S2", "S3", "S4"], index=list("ABCDE"))
    capped = apply_caps(w, sectors, position_cap=0.30, sector_cap=0.50, iterations=8)
    assert capped.sum() == pytest.approx(1.0)
    assert capped.max() < w.max()
    assert capped.groupby(sectors).sum().max() < w.groupby(sectors).sum().max()
