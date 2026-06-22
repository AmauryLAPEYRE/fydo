"""
Parité prix vs l'oracle gelé : RSI(14) Wilder + MA200.
Le drawdown N'EST PAS ici (divergence intentionnelle 252→756, SPEC §4.3) — voir
test_price_properties.py.
"""
import pathlib

import numpy as np
import pandas as pd
import pytest

from qv.brain.price import moving_average, rsi

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "oracle_golden_price.pkl"


@pytest.fixture
def price_golden():
    return pd.read_pickle(FIXTURE)


def test_rsi_latest_matches_oracle(price_golden):
    """RSI(14) dernier point == rsi_now de l'oracle, pour chaque nom du panier."""
    px = price_golden["px"]
    expected = price_golden["rsi_now"]
    for tk, ref in expected.items():
        got = rsi(px[tk], period=14).iloc[-1]
        assert got == pytest.approx(ref, abs=1e-6), f"RSI {tk}: {got} != {ref}"


def test_ma200_matches_oracle(price_golden):
    """MA200 (rolling 200 → resample mensuel) == ma200 de l'oracle, par nom."""
    px = price_golden["px"]
    expected = price_golden["ma200"]
    for tk in expected.columns:
        got = moving_average(px[tk], 200).resample("ME").last()
        np.testing.assert_allclose(
            got.to_numpy(), expected[tk].to_numpy(), atol=1e-9, equal_nan=True
        )
