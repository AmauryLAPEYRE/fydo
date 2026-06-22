"""
Invariants durs (SPEC §7) — tests qui CASSENT si un invariant dérive en douce.
Pas des property tests : des verrous.
"""
import numpy as np
import pandas as pd

from qv.brain.construct import build_portfolio, combined_score

_LEVEL = dict(interest_cov_min=2.0, net_debt_ebitda_max=3.5, fcf_ni_min=0.6, fcf_ni_max=2.0)
# Caps NON-mordants (1.0) → l'indépendance-au-score testée n'est pas masquée par un cap.
_PIPE = dict(
    weight_quality=0.5, weight_value=0.5, gate_threshold=0.0,
    level_thresholds=_LEVEL, position_cap=1.0, sector_cap=1.0, cash_buffer=0.0,
)


def test_own_history_pctile_has_zero_weight_in_combined_z():
    """combined_z = 0.5·quality_z + 0.5·value_xs_z. own_history_pctile = garde-fou,
    JAMAIS alpha (SPEC §4.3/§6). Ce test casse si quiconque la pondère : on perturbe
    own_hist_pctile sauvagement, combined_z doit être STRICTEMENT inchangé."""
    base = pd.DataFrame(
        {
            "quality_z": [1.0, -0.5, 0.3],
            "value_xs_z": [0.2, 0.8, -0.4],
            "own_hist_pctile": [0.10, 0.50, 0.90],
        },
        index=["a", "b", "c"],
    )
    perturbed = base.copy()
    perturbed["own_hist_pctile"] = [0.99, 0.01, 0.50]  # valeurs radicalement différentes

    c_base = combined_score(base, weight_quality=0.5, weight_value=0.5)
    c_perturbed = combined_score(perturbed, weight_quality=0.5, weight_value=0.5)

    pd.testing.assert_series_equal(c_base, c_perturbed)
    np.testing.assert_allclose(
        c_base.to_numpy(),
        [0.5 * 1.0 + 0.5 * 0.2, 0.5 * -0.5 + 0.5 * 0.8, 0.5 * 0.3 + 0.5 * -0.4],
    )


def _scored(combined_z_values):
    """Univers où tous passent le niveau ; combined_z imposé via quality_z
    (value_xs_z=0) → on contrôle le score sans changer l'ensemble sélectionné."""
    return pd.DataFrame(
        {
            "sector": ["A", "A", "A"],
            "quality_z": list(combined_z_values),
            "value_xs_z": [0.0, 0.0, 0.0],
            "interest_coverage": [5.0, 5.0, 5.0],
            "net_debt_ebitda": [1.0, 1.0, 1.0],
            "fcf_ni": [1.0, 1.0, 1.0],
        },
        index=["a", "b", "c"],
    )


def test_weights_are_independent_of_combined_z_score():
    """VERROU ZÉRO TILT (en indépendance-au-score, PAS égalité stricte) :
    même ensemble sélectionné + caps non-mordants → faire varier combined_z ne
    change AUCUN poids. Casse si un poids devient fonction de combined_z (tilt)."""
    low = _scored([0.5, 1.0, 1.5])    # tous ≥ gate 0 → 3 sélectionnés
    high = _scored([2.0, 0.6, 3.0])   # mêmes 3 sélectionnés, scores très différents
    w_low = build_portfolio(low, sectors=low["sector"], **_PIPE).positions["weight"]
    w_high = build_portfolio(high, sectors=high["sector"], **_PIPE).positions["weight"]
    pd.testing.assert_series_equal(w_low, w_high)


def test_level_passes_but_trend_fails_stays_selected():
    """VERROU GATING NIVEAU-SEUL : un nom au niveau OK mais tendance dégradée
    reste SÉLECTIONNÉ. La tendance (non validée) n'est jamais gating dur.
    Casse si quelqu'un câble trend_pass en exclusion."""
    df = pd.DataFrame(
        {
            "sector": ["A"],
            "quality_z": [1.0],
            "value_xs_z": [0.5],
            "interest_coverage": [5.0],
            "net_debt_ebitda": [1.0],
            "fcf_ni": [1.0],
            "margin_trend": [-0.05],  # tendance dégradée (advisory, non gating)
            "roic_trend": [-0.05],
        },
        index=["D"],
    )
    p = build_portfolio(df, sectors=df["sector"], **_PIPE)
    assert p.positions.loc["D", "status"] == "selected"
