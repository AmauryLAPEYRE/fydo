"""
Drawdown_756 — divergence intentionnelle vs oracle (252), donc testé en PROPRIÉTÉ :
bornes, calcul relatif-au-max sur fenêtre, et fail-neutral si historique < fenêtre
(garde demandée : pas de drawdown 200 j déguisé en 756).
"""
import numpy as np
import pandas as pd

from qv.brain.price import drawdown


def _series(values):
    idx = pd.date_range("2020-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype=float)


def test_drawdown_bounded_between_minus_one_and_zero():
    s = _series([10, 12, 8, 15, 7, 20, 5] + [10] * 800)
    dd = drawdown(s, window=756).dropna()
    assert (dd <= 0).all()
    assert (dd > -1).all()


def test_drawdown_insufficient_history_is_nan():
    """Moins de `window` jours → tout NaN (fail-neutral), jamais un drawdown
    calculé sur une fenêtre plus courte qu'on ferait passer pour la bonne."""
    s = _series(list(range(500)))  # 500 < 756
    dd = drawdown(s, window=756)
    assert dd.isna().all()


def test_drawdown_zero_at_new_high():
    """Au plus-haut de la fenêtre, le drawdown est exactement 0."""
    s = _series(list(range(1, 801)))  # strictement croissant → toujours au plus-haut
    dd = drawdown(s, window=756).dropna()
    np.testing.assert_allclose(dd.to_numpy(), 0.0, atol=1e-12)


def test_drawdown_known_value():
    """Plus-haut 100 dans la fenêtre de 756, prix courant 60 → drawdown -40%.
    Longueur calée à 756 pour que le 100 (position 0) reste dans la dernière fenêtre."""
    s = _series([100.0] + [90.0] * 754 + [60.0])  # len == 756
    dd = drawdown(s, window=756)
    assert dd.iloc[-1] == np.float64(60.0 / 100.0 - 1.0)
