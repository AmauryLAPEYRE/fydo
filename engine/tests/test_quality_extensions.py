"""
Extensions SPEC §4.2 absentes de l'oracle (donc hors parité) : le shrinkage
sector/univers. Testées par invariant, sans golden master.
"""
import numpy as np
import pandas as pd

from qv.brain.quality import compute_quality

W = {"m": 1.0}


def _frame(sectors, values):
    return pd.DataFrame(
        {"sector": sectors, "m": values, "nonscore": [False] * len(values)},
        index=[f"T{i}" for i in range(len(values))],
    )


def test_shrinkage_identity_when_single_sector():
    """Un seul secteur → z_secteur == z_univers → le blend est l'identité
    pour tout λ. λ=0.5 doit donner exactement λ=1.0."""
    df = _frame(["Tech"] * 5, [1.0, 2.0, 3.0, 4.0, 5.0])
    half = compute_quality(df, weights=W, shrinkage_lambda=0.5)
    full = compute_quality(df, weights=W, shrinkage_lambda=1.0)
    np.testing.assert_allclose(
        half["quality_z"].to_numpy(), full["quality_z"].to_numpy(), atol=1e-12
    )


def test_shrinkage_changes_result_across_sectors():
    """Multi-secteurs aux distributions décalées → le blend univers déplace
    réellement les z (le shrinkage a un effet), sinon λ ne sert à rien."""
    df = _frame(["A", "A", "A", "B", "B", "B"], [1.0, 2.0, 3.0, 10.0, 11.0, 12.0])
    half = compute_quality(df, weights=W, shrinkage_lambda=0.5)
    full = compute_quality(df, weights=W, shrinkage_lambda=1.0)
    assert not np.allclose(half["quality_z"].to_numpy(), full["quality_z"].to_numpy())
