"""
Feeder : transforme les réponses FMP en entrées du cerveau.
- fundamentals_frame : {ticker → bundle FMP} → DataFrame-contrat (1 ligne/nom).
- price_series : historique EOD (newest-first) → Series triée croissante.
Pures, déterministes.
"""
from __future__ import annotations

import pandas as pd

from qv.data.metrics import derive_fundamentals


def fundamentals_frame(bundles_by_ticker: dict, *, conv: dict) -> pd.DataFrame:
    rows = {tk: derive_fundamentals(bundle, **conv) for tk, bundle in bundles_by_ticker.items()}
    return pd.DataFrame.from_dict(rows, orient="index")


def price_series(historical: list) -> pd.Series:
    if not historical:
        return pd.Series(dtype=float)
    df = pd.DataFrame(historical)
    s = pd.Series(pd.to_numeric(df["close"], errors="coerce").values,
                  index=pd.to_datetime(df["date"]))
    return s.sort_index()
