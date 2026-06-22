"""
Bouclier détresse — écran fondamental (SPEC §4.4). Pur, déterministe.

Deux écrans STRICTEMENT séparés :
- level_pass : NIVEAU (couverture / levier / qualité des earnings). VALIDÉ par MC
  (prise de rang incrémentale sur le prix). → exclusion dure du bucket value.
- trend_pass : TENDANCE (pentes marge/ROIC). Advisory, NON validé, risque de
  circularité. JAMAIS gating dur en V1 ; le MC de niveau ne le valide pas.

Fail-neutral conservateur : donnée OU colonne manquante → FAIL (on ne confirme pas
la sûreté → pas d'ACCUMULER). Jamais un faux signal (SPEC §8).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    """Colonne numérique, ou série de NaN si absente (fail-neutral)."""
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def level_pass(
    df: pd.DataFrame,
    *,
    interest_cov_min: float,
    net_debt_ebitda_max: float,
    fcf_ni_min: float,
    fcf_ni_max: float,
) -> pd.Series:
    """Écran de NIVEAU (exclusion dure). True = passe le bouclier (sûr à accumuler).
    Toute comparaison contre NaN renvoie False → fail-neutral conservateur."""
    cov = _num(df, "interest_coverage")
    ndte = _num(df, "net_debt_ebitda")
    fcf_ni = _num(df, "fcf_ni")
    ok = (
        (cov >= interest_cov_min)
        & (ndte <= net_debt_ebitda_max)
        & (fcf_ni >= fcf_ni_min)
        & (fcf_ni <= fcf_ni_max)
    )
    return ok.astype(bool)


def trend_pass(
    df: pd.DataFrame,
    *,
    margin_trend_min: float,
    roic_trend_min: float,
) -> pd.Series:
    """Écran de TENDANCE (advisory, NON validé). Séparé du niveau à dessein."""
    margin = _num(df, "margin_trend")
    roic = _num(df, "roic_trend")
    ok = (margin >= margin_trend_min) & (roic >= roic_trend_min)
    return ok.astype(bool)
