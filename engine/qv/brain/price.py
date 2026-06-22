"""
Métriques prix (SPEC §4.3). Pures, déterministes, devise-neutres par nom.

- rsi(14)  : Wilder (EWM α=1/période). Parité avec l'oracle.
- moving_average(200) : rolling mean. Parité avec l'oracle (même convention).
- drawdown(756) : cours / plus-haut sur la fenêtre − 1, borné ≤ 0.
  Divergence INTENTIONNELLE vs oracle (252 j) — SPEC §4.3, cf. README gouvernance.
  Fail-neutral : historique < fenêtre → NaN (jamais un drawdown calculé sur une
  fenêtre plus courte déguisé en 756).
"""
from __future__ import annotations

import pandas as pd


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI de Wilder. Calculé sur la série sans trous (comme l'oracle).
    Cas sans perte sur la fenêtre EWM → RSI 100 (convention standard correcte) ;
    n'arrive jamais sur des prix réels multi-années (vérifié par la parité)."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100.0 - 100.0 / (1.0 + gain / loss)


def moving_average(series: pd.Series, window: int) -> pd.Series:
    """Moyenne mobile simple sur `window` jours (min_periods = window)."""
    s = pd.to_numeric(series, errors="coerce")
    return s.rolling(window).mean()


def drawdown(series: pd.Series, window: int) -> pd.Series:
    """Cours / plus-haut glissant sur `window` − 1, borné à ≤ 0.
    rolling(window) impose min_periods = window → fail-neutral si historique trop court."""
    s = pd.to_numeric(series, errors="coerce")
    rolling_max = s.rolling(window).max()
    return (s / rolling_max - 1.0).clip(upper=0.0)
