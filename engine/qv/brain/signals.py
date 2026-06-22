"""
Signaux par nom (SPEC §4.5 génériques + §5 perso). Pur, déterministe. Code NEUF.

Précédence en TABLES explicites (pas de if imbriqués) → verrouillable d'un coup.
Le `trigger` porte le pourquoi (auditabilité §8).

GÉNÉRIQUE (holding-agnostic) :
  out_of_perimeter > distress_breach (ALLÉGER) > below_gate (FILTRER)
                   > falling_knife (TENIR) > entry_ok (ACCUMULER)
  ALLÉGER générique = RÉSERVÉ à la détresse (signal négatif assez fort pour être
  émis sans connaître la détention). La saveur « cher / sous le gate » a besoin de
  savoir qu'on détient → elle vit dans la couche perso.

PERSO (holding-aware, §5 — discipline pas alpha) :
  distress_breach > below_gate_held > profit_target (ALLÉGER) > reinforce_dip (RENFORCER)
  La détresse (urgente) bat le profit-target. reinforce_dip exige « toujours
  sélectionné ». Les triggers in-perimeter ne s'appliquent qu'aux noms scorés ;
  un nom détenu hors périmètre ne reçoit que les signaux de PRIX (profit_target).
"""
from __future__ import annotations

import pandas as pd

from qv.brain.price import rsi

Rule = tuple[pd.Series, "str | None", "str | None"]


def _first_match(index: pd.Index, rules: list[Rule]) -> pd.DataFrame:
    """Première règle qui matche gagne (précédence décroissante). Table → testable
    d'un bloc ; un nom non couvert sort en signal NA (pas de signal)."""
    signal = pd.Series(pd.NA, index=index, dtype="object")
    trigger = pd.Series(pd.NA, index=index, dtype="object")
    assigned = pd.Series(False, index=index)
    for mask, sig, trig in rules:
        m = (~assigned) & mask.reindex(index, fill_value=False).astype(bool)
        signal[m] = sig
        trigger[m] = trig
        assigned |= m
    return pd.DataFrame({"signal": signal, "trigger": trigger})


def entry_filter_ok(
    price_series: pd.Series,
    *,
    rsi_period: int,
    rsi_min: float,
    no_new_low_days: int,
) -> bool:
    """Filtre d'entrée anti-couteau (discipline, PAS alpha) : prix au-dessus du
    plancher des `no_new_low_days` jours antérieurs ET RSI > plancher.
    Historique insuffisant → False (fail-neutral)."""
    s = pd.to_numeric(price_series, errors="coerce").dropna()
    if len(s) < no_new_low_days + 1:
        return False
    prior_floor = s.iloc[-(no_new_low_days + 1):-1].min()
    not_new_low = s.iloc[-1] > prior_floor
    rsi_now = rsi(s, rsi_period).iloc[-1]
    return bool(not_new_low and rsi_now > rsi_min)


def generic_signals(frame: pd.DataFrame, *, gate_threshold: float) -> pd.DataFrame:
    """Signaux génériques par nom. `frame` : combined_z, level_ok, entry_ok."""
    combined = frame["combined_z"]
    level_ok = frame["level_ok"].fillna(False).astype(bool)
    entry_ok = frame["entry_ok"].fillna(False).astype(bool)
    in_perimeter = combined.notna()
    above_gate = combined >= gate_threshold  # NaN → False

    rules: list[Rule] = [
        (~in_perimeter, None, "out_of_perimeter"),
        (~level_ok, "ALLEGER", "distress_breach"),     # détresse : bat le gate
        (~above_gate, "FILTRER", "below_gate"),
        (~entry_ok, "TENIR", "falling_knife"),
        (pd.Series(True, index=frame.index), "ACCUMULER", "entry_ok"),
    ]
    return _first_match(frame.index, rules)


def perso_signals(
    positions: pd.DataFrame,
    name_state: pd.DataFrame,
    *,
    gate_threshold: float,
    trim_low: float,
    reinforce_drop: float,
) -> pd.DataFrame:
    """Signaux perso (holding-aware). `positions` : buy_price, current_price (index
    = tickers détenus). `name_state` : combined_z, level_ok par nom."""
    held = positions.index
    st = name_state.reindex(held)

    pct = pd.to_numeric(positions["current_price"], errors="coerce") / pd.to_numeric(
        positions["buy_price"], errors="coerce"
    ) - 1.0
    in_perimeter = st["combined_z"].notna()
    level_ok = st["level_ok"].fillna(False).astype(bool)
    above_gate = st["combined_z"] >= gate_threshold

    rules: list[Rule] = [
        (in_perimeter & ~level_ok, "ALLEGER", "distress_breach"),
        (in_perimeter & ~above_gate, "ALLEGER", "below_gate_held"),
        (pct >= trim_low, "ALLEGER", "profit_target"),               # prix : périmètre-agnostic
        (in_perimeter & above_gate & level_ok & (pct <= reinforce_drop),
         "RENFORCER", "reinforce_dip"),
    ]
    out = _first_match(held, rules)
    out["pct_vs_buy"] = pct
    return out
