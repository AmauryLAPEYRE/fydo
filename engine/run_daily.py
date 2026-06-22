"""
Job quotidien : univers (règle) → fetch (cache fondamental trimestriel) → cerveau
→ écrit scores + signaux en base → delta vs run précédent → log du run (§8).

Idempotent, fail-neutral (un nom qui échoue chez FMP est droppé + loggé). Tourne en
local (pooler) ou sur GH Actions (DATABASE_URL réseau standard). Bootstrap auto-
staggéré : on ne re-fetch que les fondamentaux périmés (cache trimestriel).

Lancer : PYTHONUTF8=1 python run_daily.py [limite_univers]
"""
import datetime
import pathlib
import sys

import pandas as pd

from qv import config
from qv.brain.construct import build_portfolio, combined_score
from qv.brain.distress import level_pass
from qv.brain.price import drawdown, rsi
from qv.brain.quality import compute_quality
from qv.brain.signals import entry_filter_ok, generic_signals, perso_signals
from qv.brain.value import compute_value
from qv.data import store
from qv.data.feeder import price_series
from qv.data.fmp_client import FMPClient, FMPError
from qv.data.metrics import derive_fundamentals
from qv.data.screener import build_universe


def _env() -> dict:
    env = pathlib.Path(__file__).resolve().parents[1] / ".env"
    return {l.split("=", 1)[0]: l.split("=", 1)[1].strip()
            for l in env.read_text().splitlines() if "=" in l and not l.startswith("#")}


def _signal_delta(current: pd.DataFrame, previous: pd.DataFrame) -> pd.DataFrame:
    """Nouveaux noms + signaux changés vs le run précédent (payload in-app/alerte)."""
    rows = []
    for tk in current.index:
        new_sig, new_trig = current.loc[tk, "signal"], current.loc[tk, "trigger"]
        if tk not in previous.index:
            rows.append((tk, "—", new_sig, new_trig, "nouveau"))
        elif previous.loc[tk, "signal"] != new_sig:
            rows.append((tk, previous.loc[tk, "signal"], new_sig, new_trig, "changé"))
    return pd.DataFrame(rows, columns=["ticker", "avant", "signal", "trigger", "type"])


def run(database_url: str, fmp_key: str, as_of: datetime.date, universe_limit=None):
    client = FMPClient(fmp_key, config.FMP_BASE_URL, pause=0.3)
    conn = store.get_connection(database_url)
    conv = config.derive_conv()
    level = config.level_thresholds()
    price_start = (as_of - datetime.timedelta(days=365 * 4)).isoformat()

    # 1. Univers par règle
    screen_rows = client._get(  # company-screener (métadonnées, gratuit)
        f"company-screener?marketCapMoreThan={int(config.UNIVERSE_MIN_MARKET_CAP_USD)}"
        f"&country={config.UNIVERSE_COUNTRY}&isActivelyTrading=true&isEtf=false"
        f"&isFund=false&limit=1000")
    universe = build_universe(screen_rows, target_size=config.UNIVERSE_TARGET_SIZE_MAX,
                              exchanges=config.UNIVERSE_EXCHANGES,
                              fin_structure_keywords=config.FIN_STRUCTURE_INDUSTRY_KEYWORDS)
    if universe_limit:
        universe = universe[:universe_limit]
    store.upsert_universe(conn, universe, config.UNIVERSE_SCREEN_RULE, as_of)
    tickers = [u["ticker"] for u in universe]
    run_id = store.start_run(conn, as_of, store.config_hash(config), len(tickers))

    # 2. Fondamentaux (cache trimestriel) + prix
    cached = store.get_cached_fundamentals(conn, config.FUNDAMENTALS_REFRESH_DAYS)
    contracts, prices, dropped = {}, {}, {}
    for tk in tickers:
        try:
            if tk in getattr(cached, "index", []):
                contracts[tk] = cached.loc[tk].to_dict()
            else:
                contract = derive_fundamentals(client.fundamentals_bundle(tk, config.QUALITY_YEARS), **conv)
                store.upsert_fundamentals(conn, tk, contract)
                contracts[tk] = contract
            prices[tk] = price_series(client.historical_prices(tk, price_start))
        except FMPError as e:
            dropped[tk] = str(e)  # fail-neutral

    # 3. Cerveau
    df = pd.DataFrame.from_dict(contracts, orient="index")
    q = compute_quality(df, weights=config.QUALITY_WEIGHTS,
                        shrinkage_lambda=config.QUALITY_SHRINKAGE_LAMBDA,
                        winsor=(config.QUALITY_WINSOR_LOW, config.QUALITY_WINSOR_HIGH))
    v = compute_value(df, shrinkage_lambda=config.QUALITY_SHRINKAGE_LAMBDA,
                     winsor=(config.VALUE_WINSOR_LOW, config.VALUE_WINSOR_HIGH),
                     min_years=config.VALUE_YEARS, metrics=config.VALUE_METRICS)
    scored = df.copy()
    scored["quality_z"], scored["value_xs_z"] = q["quality_z"], v["value_xs_z"]

    dd = {tk: drawdown(s, config.PRICE_DRAWDOWN_WINDOW_DAYS).iloc[-1] for tk, s in prices.items()}
    rsi_now = {tk: rsi(s, config.PRICE_RSI_PERIOD).iloc[-1] for tk, s in prices.items()}
    entry_ok = {tk: entry_filter_ok(s, rsi_period=config.PRICE_RSI_PERIOD,
                                    rsi_min=config.ENTRY_RSI_MIN,
                                    no_new_low_days=config.ENTRY_NO_NEW_LOW_DAYS)
                for tk, s in prices.items()}

    sig_frame = pd.DataFrame(index=scored.index)
    sig_frame["combined_z"] = combined_score(scored, config.COMBINED_Z_WEIGHT_QUALITY,
                                             config.COMBINED_Z_WEIGHT_VALUE)
    sig_frame["level_ok"] = level_pass(scored, **level)
    sig_frame["entry_ok"] = pd.Series(entry_ok).reindex(scored.index).fillna(False)
    gen = generic_signals(sig_frame, gate_threshold=config.GATE_COMBINED_Z)

    # 4. Scores (audit §8) + signaux
    scores_df = pd.DataFrame(index=scored.index)
    scores_df["quality_z"] = q["quality_z"]
    scores_df["quality_pct"] = q["quality_pct"]
    scores_df["value_xs_z"] = v["value_xs_z"]
    scores_df["combined_z"] = sig_frame["combined_z"]
    scores_df["drawdown_756"] = pd.Series(dd).reindex(scored.index)
    scores_df["rsi_14"] = pd.Series(rsi_now).reindex(scored.index)
    for c in ("interest_coverage", "net_debt_ebitda", "fcf_ni"):
        scores_df[c] = scored[c]
    scores_df["gate_pass"] = sig_frame["combined_z"] >= config.GATE_COMBINED_Z
    scores_df["distress_pass"] = sig_frame["level_ok"]

    prev = store.get_previous_signals(conn, as_of)
    delta = _signal_delta(gen, prev)

    store.write_scores(conn, as_of, scores_df)
    store.write_signals(conn, as_of, gen)

    # 5. Signaux perso (croise positions, si saisies)
    positions = store.get_positions(conn)
    if not positions.empty:
        held = positions.set_index("ticker")
        state = pd.DataFrame({"combined_z": sig_frame["combined_z"], "level_ok": sig_frame["level_ok"]})
        held["current_price"] = [prices[tk].iloc[-1] if tk in prices else None for tk in held.index]
        perso = perso_signals(held[["buy_price", "current_price"]], state,
                              gate_threshold=config.GATE_COMBINED_Z,
                              trim_low=config.PERSO_TRIM_LOW, reinforce_drop=config.PERSO_REINFORCE_DROP)
        # (écriture signals_perso : à câbler avec user_id réel quand positions saisies)

    store.finish_run(conn, run_id, "partial" if dropped else "ok", len(contracts), dropped)
    conn.close()
    return gen, delta, dropped


def main():
    env = _env()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    as_of = datetime.date.today()
    gen, delta, dropped = run(env["DATABASE_URL"], env["FMP_API_KEY"], as_of, universe_limit=limit)
    if dropped:
        print("DROPPÉS (fail-neutral) :", dropped)
    print(f"\n=== RUN {as_of} — {len(gen)} noms scorés ===")
    print("Répartition :", gen["signal"].value_counts(dropna=False).to_dict())
    print(f"\nDELTA vs run précédent ({len(delta)} changements) :")
    print(delta.to_string(index=False) if not delta.empty else "  (aucun — premier run ou rien changé)")


if __name__ == "__main__":
    main()
