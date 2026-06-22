"""
Signaux par nom (SPEC §4.5 génériques + §5 perso). Code NEUF, pas d'oracle.
Conventions actées (tranchées sans oracle, documentées) :

GÉNÉRIQUE (holding-agnostic) — précédence en table :
  out_of_perimeter > distress_breach (ALLÉGER) > below_gate (FILTRER)
                   > falling_knife (TENIR) > entry_ok (ACCUMULER)
  ALLÉGER générique = RÉSERVÉ à la détresse (assez fort pour être sans détention).
  TENIR = sélectionné mais pas achetable (couteau qui tombe).

PERSO (holding-aware) — précédence en table, sur les noms détenus :
  distress_breach > below_gate_held > profit_target (ALLÉGER) > reinforce_dip (RENFORCER)
  La détresse (urgente) bat le profit-target. reinforce_dip exige « toujours sélectionné ».
"""
import numpy as np
import pandas as pd
import pytest

from qv.brain.signals import entry_filter_ok, generic_signals, perso_signals

ENTRY = dict(rsi_period=14, rsi_min=30.0, no_new_low_days=20)


def _g(rows):
    return generic_signals(pd.DataFrame(rows).set_index("tk"), gate_threshold=0.0)


# ── GÉNÉRIQUE ──
def test_out_of_perimeter_emits_no_signal():
    out = _g([{"tk": "X", "combined_z": np.nan, "level_ok": True, "entry_ok": True}])
    assert pd.isna(out.loc["X", "signal"])
    assert out.loc["X", "trigger"] == "out_of_perimeter"


def test_distress_breach_wins_over_gate_regardless():
    """Bouclier cassé → ALLÉGER distress_breach, sous OU au-dessus du gate."""
    out = _g([
        {"tk": "BELOW", "combined_z": -1.0, "level_ok": False, "entry_ok": True},
        {"tk": "ABOVE", "combined_z": 1.0, "level_ok": False, "entry_ok": False},
    ])
    assert (out["signal"] == "ALLEGER").all()
    assert (out["trigger"] == "distress_breach").all()


def test_below_gate_shield_ok_is_filtrer():
    out = _g([{"tk": "F", "combined_z": -0.5, "level_ok": True, "entry_ok": True}])
    assert out.loc["F", "signal"] == "FILTRER"
    assert out.loc["F", "trigger"] == "below_gate"


def test_selected_and_stabilized_is_accumuler():
    out = _g([{"tk": "A", "combined_z": 1.0, "level_ok": True, "entry_ok": True}])
    assert out.loc["A", "signal"] == "ACCUMULER"
    assert out.loc["A", "trigger"] == "entry_ok"


def test_selected_but_falling_knife_is_tenir():
    out = _g([{"tk": "T", "combined_z": 1.0, "level_ok": True, "entry_ok": False}])
    assert out.loc["T", "signal"] == "TENIR"
    assert out.loc["T", "trigger"] == "falling_knife"


# ── FILTRE D'ENTRÉE ──
def _series(vals):
    idx = pd.date_range("2020-01-01", periods=len(vals), freq="D")
    return pd.Series(vals, index=idx, dtype=float)


def test_entry_ok_when_rising_and_above_recent_floor():
    assert entry_filter_ok(_series(list(range(1, 40))), **ENTRY) is True


def test_entry_blocked_on_new_20d_low():
    assert entry_filter_ok(_series(list(range(1, 40)) + [0.0]), **ENTRY) is False


def test_entry_blocked_when_rsi_below_floor():
    assert entry_filter_ok(_series(list(range(40, 1, -1))), **ENTRY) is False


def test_entry_insufficient_history_fails_neutral():
    assert entry_filter_ok(_series(list(range(1, 10))), **ENTRY) is False


# ── PERSO ──
def _perso(positions_rows, state_rows, **kw):
    pos = pd.DataFrame(positions_rows).set_index("tk")
    st = pd.DataFrame(state_rows).set_index("tk")
    return perso_signals(pos, st, gate_threshold=0.0, trim_low=0.40,
                         reinforce_drop=-0.15, **kw)


def test_perso_profit_target_when_up_past_band():
    out = _perso(
        [{"tk": "P", "buy_price": 100.0, "current_price": 147.0}],
        [{"tk": "P", "combined_z": 1.0, "level_ok": True}],
    )
    assert out.loc["P", "signal"] == "ALLEGER"
    assert out.loc["P", "trigger"] == "profit_target"
    assert out.loc["P", "pct_vs_buy"] == pytest.approx(0.47)


def test_perso_reinforce_when_down_and_still_selected():
    out = _perso(
        [{"tk": "R", "buy_price": 100.0, "current_price": 82.0}],
        [{"tk": "R", "combined_z": 1.0, "level_ok": True}],
    )
    assert out.loc["R", "signal"] == "RENFORCER"
    assert out.loc["R", "trigger"] == "reinforce_dip"


def test_perso_below_gate_held_is_alleger():
    out = _perso(
        [{"tk": "B", "buy_price": 100.0, "current_price": 100.0}],
        [{"tk": "B", "combined_z": -1.0, "level_ok": True}],
    )
    assert out.loc["B", "signal"] == "ALLEGER"
    assert out.loc["B", "trigger"] == "below_gate_held"


def test_perso_distress_beats_profit_target():
    """Détenu + détresse + up 45% → distress_breach (urgent) bat profit_target."""
    out = _perso(
        [{"tk": "D", "buy_price": 100.0, "current_price": 145.0}],
        [{"tk": "D", "combined_z": 1.0, "level_ok": False}],
    )
    assert out.loc["D", "trigger"] == "distress_breach"


def test_perso_out_of_perimeter_held_still_gets_price_signal():
    """Nom hors périmètre détenu : pas de distress fabriqué, mais profit_target
    (prix) s'applique quand même."""
    out = _perso(
        [{"tk": "O", "buy_price": 100.0, "current_price": 150.0}],
        [{"tk": "O", "combined_z": np.nan, "level_ok": False}],
    )
    assert out.loc["O", "trigger"] == "profit_target"


def test_perso_selected_and_flat_no_signal():
    out = _perso(
        [{"tk": "H", "buy_price": 100.0, "current_price": 105.0}],
        [{"tk": "H", "combined_z": 1.0, "level_ok": True}],
    )
    assert pd.isna(out.loc["H", "signal"])
