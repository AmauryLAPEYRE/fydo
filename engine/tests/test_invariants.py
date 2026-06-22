"""
Invariants durs (SPEC §7) — tests qui CASSENT si un invariant dérive en douce.
Pas des property tests : des verrous.
"""
import numpy as np
import pandas as pd

from qv.brain.construct import combined_score


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
