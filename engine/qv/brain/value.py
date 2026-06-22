"""
Score value — yields EV-based, normalisés 5 ans, cross-sectional (SPEC §4.3).
Pur, déterministe. Code NEUF (l'oracle n'a pas de value) — conventions documentées.

- Yields (jamais multiples) : FCF/EV · EBIT/EV · E/P. EV-based = neutre à la
  structure de capital (sinon value récompense le levier que qualité pénalise).
- Numérateur = moyenne 5 ans (FCF_5y/EBIT_5y/NI_5y) sur EV/mktcap COURANTS
  (Graham-Dodd, anti-piège cyclique). JAMAIS TTM.
- value_xs_z = moyenne des z(yields) DISPONIBLES, sector-neutral + shrinkage.
- own_history_pctile = GARDE-FOU / tie-break SEULEMENT, JAMAIS pondéré en alpha
  (combined_z a un poids ZÉRO dessus — cf. test_invariants).

Fail-neutral : historique < min_years, EV≤0, mktcap≤0 ou donnée manquante →
sous-métrique NaN (moyennée sur les disponibles) ; aucun value score fabriqué.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qv.brain._scoring import Winsor, numeric_or_nan, sector_neutral_z


def compute_yields(df: pd.DataFrame, min_years: int) -> pd.DataFrame:
    """EV + trois yields par nom. Sous-métrique indéfinie → NaN (fail-neutral)."""
    mktcap = numeric_or_nan(df, "mktcap")
    debt = numeric_or_nan(df, "total_debt")
    cash = numeric_or_nan(df, "cash")
    fcf = numeric_or_nan(df, "fcf_5y")
    ebit = numeric_or_nan(df, "ebit_5y")
    ni = numeric_or_nan(df, "ni_5y")
    years = numeric_or_nan(df, "years_available")

    enough = years >= min_years
    ev = mktcap + debt - cash
    ev_ok = enough & (ev > 0)        # EV≤0 → FCF/EV, EBIT/EV indéfinis
    mc_ok = enough & (mktcap > 0)    # E/P défini tant que la capi est positive

    out = pd.DataFrame(index=df.index)
    out["ev"] = ev
    out["fcf_ev"] = (fcf / ev).where(ev_ok)
    out["ebit_ev"] = (ebit / ev).where(ev_ok)
    out["e_p"] = (ni / mktcap).where(mc_ok)
    return out


def compute_value(
    df: pd.DataFrame,
    *,
    shrinkage_lambda: float,
    winsor: Winsor,
    min_years: int,
    metrics: tuple[str, ...],
    sector_col: str = "sector",
    nonscore_col: str = "nonscore",
) -> pd.DataFrame:
    """value_xs_z par nom (NaN pour nonscore / historique court / yields tous NaN)."""
    yields = compute_yields(df, min_years)
    scor_mask = ~df[nonscore_col].astype(bool)

    work = df.loc[scor_mask, [sector_col]].copy()
    for m in metrics:
        work[m] = yields.loc[scor_mask, m]

    z_by_metric = {
        m: sector_neutral_z(work, m, sector_col, shrinkage_lambda, winsor)
        for m in metrics
    }
    z = pd.DataFrame(z_by_metric, index=work.index)
    value_xs_z = z.mean(axis=1, skipna=True)  # moyenne sur les sous-métriques dispo

    out = pd.DataFrame(index=df.index)
    out["value_xs_z"] = value_xs_z.reindex(df.index)
    return out


def own_history_pctile(current: float, history) -> float:
    """Percentile du yield courant vs sa propre histoire. GARDE-FOU seulement.
    Fraction de l'historique strictement sous le courant ∈ [0, 1]."""
    h = pd.to_numeric(pd.Series(list(history)), errors="coerce").dropna()
    if len(h) == 0 or pd.isna(current):
        return np.nan
    return float((h < current).mean())
