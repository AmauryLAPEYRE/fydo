"""
Machinerie de scoring partagée (qualité & value) : winsorisation, z-score,
neutralité sectorielle, shrinkage sector/univers. Pure, déterministe.

Convention sector-neutral + shrinkage (SPEC §4.2/§4.3) :
    z_final = λ · z_secteur + (1-λ) · z_univers      (λ=1 → z pur intra-secteur)
winsor et z se font INTRA-secteur (comme l'oracle) ; le terme univers est un blend
qui stabilise les petits buckets.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

Winsor = tuple[float, float]


def numeric_or_nan(df: pd.DataFrame, col: str) -> pd.Series:
    """Colonne numérique, ou série de NaN si la colonne est absente (fail-neutral)."""
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def winsor(s: pd.Series, bounds: Winsor) -> pd.Series:
    lo, hi = bounds
    s = pd.to_numeric(s, errors="coerce")
    return s.clip(s.quantile(lo), s.quantile(hi))


def zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    if sd and not np.isnan(sd):
        return (s - s.mean()) / sd
    return s * 0.0  # std nul/indéfini (bucket à 1 nom) → contribution neutre


def sector_z(frame: pd.DataFrame, col: str, sector_col: str, bounds: Winsor) -> pd.Series:
    return frame.groupby(sector_col, group_keys=False)[col].apply(
        lambda g: zscore(winsor(g, bounds))
    )


def universe_z(frame: pd.DataFrame, col: str, bounds: Winsor) -> pd.Series:
    return zscore(winsor(frame[col], bounds))


def sector_neutral_z(
    frame: pd.DataFrame,
    col: str,
    sector_col: str,
    shrinkage_lambda: float,
    bounds: Winsor,
) -> pd.Series:
    """z sector-neutral, shrinké vers l'univers. λ=1 → z pur intra-secteur (oracle)."""
    z_sec = sector_z(frame, col, sector_col, bounds)
    if shrinkage_lambda < 1.0:
        z_uni = universe_z(frame, col, bounds)
        return shrinkage_lambda * z_sec + (1.0 - shrinkage_lambda) * z_uni
    return z_sec
