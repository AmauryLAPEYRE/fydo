"""
Score qualité — sector-neutral, 5 ans, winsorisé, shrinké (SPEC §4.2).

Pure : mêmes entrées → même sortie (déterminisme SPEC §7). Aucune I/O.
Le flag `nonscore` (FIN_STRUCTURE) est un INPUT — les non-scorables sortent en NaN.

Paramétré pour que la PARITÉ tienne : avec les poids de l'oracle (5 métriques) et
shrinkage_lambda=1.0 (z pur intra-secteur, sans blend univers), reproduit au point
près le quality_pct de qv_engine_v4.py. Aux défauts de config (6 métriques +
couverture d'intérêts, λ=0.5), implémente l'extension SPEC §4.2.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _winsor(s: pd.Series, lo: float, hi: float) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    return s.clip(s.quantile(lo), s.quantile(hi))


def _zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    if sd and not np.isnan(sd):
        return (s - s.mean()) / sd
    return s * 0.0  # std nul/indéfini (groupe à 1 nom) → contribution neutre


def _sector_z(frame: pd.DataFrame, col: str, sector_col: str,
              winsor: tuple[float, float]) -> pd.Series:
    lo, hi = winsor
    return frame.groupby(sector_col, group_keys=False)[col].apply(
        lambda g: _zscore(_winsor(g, lo, hi))
    )


def _universe_z(frame: pd.DataFrame, col: str, winsor: tuple[float, float]) -> pd.Series:
    lo, hi = winsor
    return _zscore(_winsor(frame[col], lo, hi))


def compute_quality(
    df: pd.DataFrame,
    weights: dict[str, float],
    shrinkage_lambda: float,
    winsor: tuple[float, float] = (0.05, 0.95),
    sector_col: str = "sector",
    nonscore_col: str = "nonscore",
) -> pd.DataFrame:
    """Retourne un DataFrame indexé comme `df` avec quality_z et quality_pct.
    Les noms `nonscore` (FIN_STRUCTURE) sortent en NaN (exclus du z et du rang).
    `shrinkage_lambda` : z_final = λ·z_secteur + (1-λ)·z_univers (λ=1 → oracle)."""
    scor = df[~df[nonscore_col].astype(bool)].copy()

    acc = pd.Series(0.0, index=scor.index)
    wsum = 0.0
    for col, w in weights.items():
        if col not in scor.columns:
            continue  # métrique absente → ignorée (fail-neutral, comme l'oracle)
        z_sec = _sector_z(scor, col, sector_col, winsor)
        if shrinkage_lambda < 1.0:
            z_uni = _universe_z(scor, col, winsor)
            z = shrinkage_lambda * z_sec + (1.0 - shrinkage_lambda) * z_uni
        else:
            z = z_sec
        acc = acc.add(w * z.fillna(0), fill_value=0)
        wsum += abs(w)

    quality_z = acc / wsum
    quality_pct = quality_z.rank(pct=True)

    out = pd.DataFrame(index=df.index)
    out["quality_z"] = quality_z.reindex(df.index)
    out["quality_pct"] = quality_pct.reindex(df.index)
    return out
