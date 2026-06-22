"""
Score qualité — sector-neutral, 5 ans, winsorisé, shrinké (SPEC §4.2).

Pure : mêmes entrées → même sortie (déterminisme SPEC §7). Aucune I/O.
Le flag `nonscore` (FIN_STRUCTURE) est un INPUT — les non-scorables sortent en NaN.

Paramétré pour que la PARITÉ tienne : avec les poids de l'oracle (5 métriques) et
shrinkage_lambda=1.0 (z pur intra-secteur), reproduit au point près le quality_pct
de qv_engine_v4.py. Aux défauts de config (6 métriques + couverture d'intérêts,
λ=0.5), implémente l'extension SPEC §4.2.
"""
from __future__ import annotations

import pandas as pd

from qv.brain._scoring import sector_neutral_z


def compute_quality(
    df: pd.DataFrame,
    weights: dict[str, float],
    shrinkage_lambda: float,
    winsor: tuple[float, float] = (0.05, 0.95),
    sector_col: str = "sector",
    nonscore_col: str = "nonscore",
) -> pd.DataFrame:
    """Retourne un DataFrame indexé comme `df` avec quality_z et quality_pct.
    Les noms `nonscore` (FIN_STRUCTURE) sortent en NaN (exclus du z et du rang)."""
    scor = df[~df[nonscore_col].astype(bool)].copy()

    acc = pd.Series(0.0, index=scor.index)
    wsum = 0.0
    for col, w in weights.items():
        if col not in scor.columns:
            continue  # métrique absente → ignorée (fail-neutral, comme l'oracle)
        z = sector_neutral_z(scor, col, sector_col, shrinkage_lambda, winsor)
        acc = acc.add(w * z.fillna(0), fill_value=0)
        wsum += abs(w)

    quality_z = acc / wsum
    quality_pct = quality_z.rank(pct=True)

    out = pd.DataFrame(index=df.index)
    out["quality_z"] = quality_z.reindex(df.index)
    out["quality_pct"] = quality_pct.reindex(df.index)
    return out
