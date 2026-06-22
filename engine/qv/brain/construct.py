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

import pandas as pd


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
