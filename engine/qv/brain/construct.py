"""
Construction de portefeuille (SPEC §4.6/§4.7). Pure, déterministe.

Cœur = gated EQUAL-WEIGHT sur les noms sélectionnés. **AUCUN tilt de magnitude**
(SPEC §4.7 : tilt drawdown falsifié → interdit ; ne pas pondérer ∝ drawdown ni ∝ z).
Plafonds = filet de sécurité (position 8% / secteur 30%), algo itératif porté tel
quel de l'oracle (trou de spec → convention oracle, cf. README gouvernance).

Le pipeline complet (combined_z = 0.5·quality_z + 0.5·value_z → drop détresse →
gate → equal_weight → caps → coussin de cash) s'assemble au Step 3, quand value.py
et distress.py existent. Ici : les primitives réutilisables.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from qv.brain.distress import level_pass

# Statuts explicites par nom (auditabilité §8) — pas de poids 0 muet.
STATUS_SELECTED = "selected"
STATUS_BELOW_GATE = "below_gate"
STATUS_DISTRESS = "distress_excluded"
STATUS_OUT = "out_of_perimeter"


@dataclass(frozen=True)
class Portfolio:
    """positions : index=nom, colonnes [combined_z, status, weight]. cash : fraction.
    Invariant : positions['weight'].sum() + cash == 1.0."""
    positions: pd.DataFrame
    cash: float


def combined_score(
    df: pd.DataFrame, weight_quality: float, weight_value: float
) -> pd.Series:
    """combined_z = w_q·quality_z + w_v·value_xs_z (priors 0.5/0.5, JAMAIS tunés —
    SPEC §7.1). N'utilise QUE quality_z et value_xs_z : own_history_pctile a un poids
    ZÉRO (garde-fou, jamais alpha — SPEC §4.3/§6). Verrouillé par test_invariants."""
    return weight_quality * df["quality_z"] + weight_value * df["value_xs_z"]


def gate_mask(score: pd.Series, threshold: float) -> pd.Series:
    """Sélection ordinale : score ≥ seuil (prior, jamais fitté — SPEC §7.1)."""
    return score >= threshold


def equal_weight(mask: pd.Series) -> pd.Series:
    """Equal-weight sur les noms gated (mask True). Renormalisé à 1.
    Les non-sélectionnés sortent à 0. AUCUN tilt."""
    g = mask.astype(float)
    return g / g.sum()


def gated_equal_weight(score: pd.Series, threshold: float) -> pd.Series:
    """Primitive de construction : gate ordinal puis equal-weight."""
    return equal_weight(gate_mask(score, threshold))


def apply_caps(
    weights: pd.Series,
    sectors: pd.Series,
    position_cap: float,
    sector_cap: float,
    iterations: int = 8,
) -> pd.Series:
    """Plafonne position et secteur par clip + renormalisation itératifs.
    Filet non-contraignant sur le livre actuel (SPEC §4.7). Porté tel quel de
    l'oracle ; `weights` et `sectors` doivent partager le même ordre d'index."""
    w = weights.copy()
    for _ in range(iterations):
        w = w.clip(upper=position_cap)
        w = w / w.sum()
        sector_sums = w.groupby(sectors).sum()
        over = sector_sums[sector_sums > sector_cap]
        if over.empty and (w <= position_cap + 1e-9).all():
            break
        for s in over.index:
            in_sector = (sectors == s).values
            w[in_sector] *= sector_cap / sector_sums[s]
        w = w / w.sum()
    return w


def build_portfolio(
    df: pd.DataFrame,
    sectors: pd.Series,
    *,
    weight_quality: float,
    weight_value: float,
    gate_threshold: float,
    level_thresholds: Mapping[str, float],
    position_cap: float,
    sector_cap: float,
    cash_buffer: float,
) -> Portfolio:
    """Assemble le livre (SPEC §4.6) : combined_z → drop NIVEAU détresse → gate →
    equal_weight (ZÉRO tilt) → caps → coussin de cash fixe. Statut explicite par nom.

    Seul l'écran de NIVEAU est gating dur (la tendance n'entre jamais ici). Sélection
    vide → 100 % cash (fail-neutral, pas de division par zéro)."""
    sectors = sectors.reindex(df.index)
    combined = combined_score(df, weight_quality, weight_value)
    passes_level = level_pass(df, **level_thresholds)

    # Statut, par précédence croissante (la dernière affectation gagne) :
    # selected < below_gate < distress_excluded < out_of_perimeter.
    status = pd.Series(STATUS_SELECTED, index=df.index)
    status[combined < gate_threshold] = STATUS_BELOW_GATE     # NaN < seuil → False
    status[~passes_level] = STATUS_DISTRESS                   # niveau seul
    status[combined.isna()] = STATUS_OUT                      # ni quality ni value

    selected = status == STATUS_SELECTED
    positions = pd.DataFrame(index=df.index)
    positions["combined_z"] = combined
    positions["status"] = status

    if not selected.any():
        positions["weight"] = 0.0
        return Portfolio(positions=positions, cash=1.0)

    capped = apply_caps(equal_weight(selected), sectors, position_cap, sector_cap)
    positions["weight"] = capped * (1.0 - cash_buffer)
    return Portfolio(positions=positions, cash=cash_buffer)
