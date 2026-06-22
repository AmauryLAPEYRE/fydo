"""
Run end-to-end LIVE (démo, sans DB) : FMP → contrat → cerveau complet → signaux.
Preuve que « migration yfinance→FMP sans changer le cerveau » tient en bout de chaîne.

Univers = watchlist US illustrative (multi-secteurs + 1 financière pour exercer le
flag nonscore). PAS un univers de backtest — aucune claim de perf (live_watchlist).
Lancer : PYTHONUTF8=1 python run_live_demo.py
"""
import pathlib
import sys

import pandas as pd

from qv import config
from qv.brain.construct import build_portfolio, combined_score
from qv.brain.distress import level_pass
from qv.brain.price import drawdown, rsi
from qv.brain.quality import compute_quality
from qv.brain.signals import entry_filter_ok, generic_signals
from qv.brain.value import compute_value
from qv.data.feeder import fundamentals_frame, price_series
from qv.data.fmp_client import FMPClient, FMPError

WATCHLIST = ["AAPL", "MSFT", "JNJ", "PG", "KO", "XOM", "CAT", "HD", "UNH", "JPM"]
CONV = dict(
    fin_structure_keywords=config.FIN_STRUCTURE_INDUSTRY_KEYWORDS,
    tax_default=config.TAX_RATE_DEFAULT, tax_min=config.TAX_RATE_MIN,
    tax_max=config.TAX_RATE_MAX, interest_coverage_cap=config.INTEREST_COVERAGE_CAP,
)
LEVEL = dict(
    interest_cov_min=config.SHIELD_INTEREST_COVERAGE_MIN,
    net_debt_ebitda_max=config.SHIELD_NET_DEBT_EBITDA_MAX,
    fcf_ni_min=config.SHIELD_FCF_TO_NI_MIN, fcf_ni_max=config.SHIELD_FCF_TO_NI_MAX,
)


def _api_key() -> str:
    env = pathlib.Path(__file__).resolve().parents[1] / ".env"
    for line in env.read_text().splitlines():
        if line.startswith("FMP_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("FMP_API_KEY absent de .env")


def main():
    client = FMPClient(_api_key(), config.FMP_BASE_URL, pause=0.35)  # pause anti-throttle
    bundles, prices, dropped = {}, {}, {}
    for tk in WATCHLIST:
        try:
            bundles[tk] = client.fundamentals_bundle(tk, config.QUALITY_YEARS)
            prices[tk] = price_series(client.historical_prices(tk, "2021-01-01"))
        except FMPError as e:
            dropped[tk] = str(e)  # fail-neutral : droppé + loggé, jamais un faux signal
    if dropped:
        print("DROPPÉS (fail-neutral) :", dropped)

    df = fundamentals_frame(bundles, conv=CONV)
    q = compute_quality(df, weights=config.QUALITY_WEIGHTS,
                        shrinkage_lambda=config.QUALITY_SHRINKAGE_LAMBDA,
                        winsor=(config.QUALITY_WINSOR_LOW, config.QUALITY_WINSOR_HIGH))
    v = compute_value(df, shrinkage_lambda=config.QUALITY_SHRINKAGE_LAMBDA,
                     winsor=(config.VALUE_WINSOR_LOW, config.VALUE_WINSOR_HIGH),
                     min_years=config.VALUE_YEARS, metrics=config.VALUE_METRICS)
    scored = df.copy()
    scored["quality_z"] = q["quality_z"]
    scored["value_xs_z"] = v["value_xs_z"]

    # métriques prix par nom
    dd = {tk: drawdown(s, config.PRICE_DRAWDOWN_WINDOW_DAYS).iloc[-1] for tk, s in prices.items()}
    rsi_now = {tk: rsi(s, config.PRICE_RSI_PERIOD).iloc[-1] for tk, s in prices.items()}
    entry_ok = {tk: entry_filter_ok(s, rsi_period=config.PRICE_RSI_PERIOD,
                                    rsi_min=config.ENTRY_RSI_MIN,
                                    no_new_low_days=config.ENTRY_NO_NEW_LOW_DAYS)
                for tk, s in prices.items()}

    sig_frame = pd.DataFrame(index=scored.index)
    sig_frame["combined_z"] = combined_score(scored, config.COMBINED_Z_WEIGHT_QUALITY,
                                             config.COMBINED_Z_WEIGHT_VALUE)
    sig_frame["level_ok"] = level_pass(scored, **LEVEL)
    sig_frame["entry_ok"] = pd.Series(entry_ok).reindex(scored.index).fillna(False)
    sig = generic_signals(sig_frame, gate_threshold=config.GATE_COMBINED_Z)

    book = build_portfolio(
        scored, sectors=scored["sector"],
        weight_quality=config.COMBINED_Z_WEIGHT_QUALITY,
        weight_value=config.COMBINED_Z_WEIGHT_VALUE, gate_threshold=config.GATE_COMBINED_Z,
        level_thresholds=LEVEL, position_cap=config.CAP_POSITION,
        sector_cap=config.CAP_SECTOR, cash_buffer=config.CASH_BUFFER_FRACTION,
    )

    out = pd.DataFrame({
        "sector": scored["sector"].str[:14],
        "combined_z": sig_frame["combined_z"].round(2),
        "dd_3y%": pd.Series(dd).reindex(scored.index).mul(100).round(0),
        "rsi": pd.Series(rsi_now).reindex(scored.index).round(0),
        "signal": sig["signal"],
        "trigger": sig["trigger"],
        "poids%": (book.positions["weight"] * 100).round(1),
    }).sort_values("combined_z", ascending=False, na_position="last")

    print("\n" + "=" * 92)
    print(f"SIGNAUX LIVE (FMP, {len(df)} noms US) — cash {book.cash * 100:.0f}%")
    print("=" * 92)
    print(out.to_string())
    print("\nRépartition des signaux :", sig["signal"].value_counts(dropna=False).to_dict())


if __name__ == "__main__":
    main()
