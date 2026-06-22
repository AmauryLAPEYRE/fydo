"""
Parité du cerveau vs l'oracle gelé qv_engine_v4.py.

Portée (SPEC §0, actée à deux) : parité = le CŒUR PRÉSERVÉ uniquement
(winsor intra-secteur → z intra-secteur → somme pondérée → rank percentile).
Le tilt de v4 est EXCLU (mort, interdit de le porter). Les extensions SPEC
(couverture d'intérêts +0.5, shrinkage λ=0.5) diffèrent de l'oracle PAR DESIGN
et ont leurs tests propres — ici on rejoue l'oracle avec SES paramètres pour
prouver que la mécanique de calcul ne dérive pas.
"""
import pathlib

import numpy as np
import pandas as pd
import pytest

from qv.brain.quality import compute_quality

# Poids EXACTS de l'oracle (5 métriques, SANS couverture d'intérêts).
# Pinnés ici, PAS importés de config (= mode prod, 6 métriques + shrinkage).
ORACLE_WEIGHTS = {
    "roic_5y_avg": 1.5,
    "gross_margin_5y_avg": 1.0,
    "net_margin_5y_avg": 1.0,
    "rev_cagr_5y": 0.7,
    "debt_to_equity": -1.0,
}

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "oracle_golden_quality.pkl"


@pytest.fixture
def golden():
    return pd.read_pickle(FIXTURE)


def test_quality_pct_matches_oracle(golden):
    """quality_pct reproduit au point près l'oracle en mode oracle
    (poids 5 métriques, λ=1.0 = z pur intra-secteur, sans blend univers)."""
    out = compute_quality(
        golden,
        weights=ORACLE_WEIGHTS,
        shrinkage_lambda=1.0,
        winsor=(0.05, 0.95),
    )
    expected = golden["quality_pct"]

    # Mêmes non-scorables (FIN_STRUCTURE → quality_pct NaN).
    pd.testing.assert_series_equal(
        out["quality_pct"].isna(), expected.isna(), check_names=False
    )
    # Égalité numérique sur les scorables.
    mask = ~expected.isna()
    np.testing.assert_allclose(
        out.loc[mask, "quality_pct"].to_numpy(),
        expected[mask].to_numpy(),
        atol=1e-9,
    )
