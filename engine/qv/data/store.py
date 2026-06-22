"""
Persistance Supabase (Postgres). Job backend = role postgres via pooler (bypass RLS).
Connexion pooler transaction-mode → prepare_threshold=None. NaN/NaT → NULL.

Auditabilité §8 : start_run/finish_run loggent chaque run (config_hash, comptes,
noms droppés). scores = trace de chaque signal à ses entrées.
"""
from __future__ import annotations

import hashlib
import inspect
import json

import pandas as pd
import psycopg


def get_connection(database_url: str):
    return psycopg.connect(database_url, autocommit=True, prepare_threshold=None)


def config_hash(config_module) -> str:
    """Hash de la config nommée → runs.config_hash (rejouabilité, déterminisme §7)."""
    src = inspect.getsource(config_module).encode("utf-8")
    return hashlib.sha256(src).hexdigest()[:16]


def _clean(v):
    """numpy/pandas → python natif ; NaN/NaT → None (NULL)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):
        return v.item()
    return v


def upsert_universe(conn, rows: list[dict], screen_rule: str, screened_at) -> None:
    sql = """insert into universe
               (ticker,name,sector,currency,is_fin_structure,active,screen_rule,screened_at)
             values (%(ticker)s,%(name)s,%(sector)s,%(currency)s,%(is_fin_structure)s,
                     true,%(screen_rule)s,%(screened_at)s)
             on conflict (ticker) do update set
               name=excluded.name, sector=excluded.sector, currency=excluded.currency,
               is_fin_structure=excluded.is_fin_structure, active=true,
               screen_rule=excluded.screen_rule, screened_at=excluded.screened_at"""
    payload = [{**{k: _clean(v) for k, v in r.items()},
                "screen_rule": screen_rule, "screened_at": screened_at} for r in rows]
    with conn.cursor() as cur:
        cur.executemany(sql, payload)


FUND_COLS = ["sector", "nonscore", "currency", "mktcap", "roic_5y_avg",
             "gross_margin_5y_avg", "net_margin_5y_avg", "rev_cagr_5y", "debt_to_equity",
             "interest_coverage", "net_debt_ebitda", "fcf_ni", "margin_trend", "roic_trend",
             "fcf_5y", "ebit_5y", "ni_5y", "total_debt", "cash", "years_available"]


def upsert_fundamentals(conn, ticker: str, contract: dict) -> None:
    cols = ",".join(FUND_COLS)
    placeholders = ",".join(f"%({c})s" for c in FUND_COLS)
    updates = ",".join(f"{c}=excluded.{c}" for c in FUND_COLS)
    sql = (f"insert into fundamentals_cache (ticker,{cols},fetched_at) "
           f"values (%(ticker)s,{placeholders},now()) "
           f"on conflict (ticker) do update set {updates}, fetched_at=now()")
    row = {"ticker": ticker, **{c: _clean(contract.get(c)) for c in FUND_COLS}}
    conn.execute(sql, row)


def get_cached_fundamentals(conn, max_age_days: int) -> pd.DataFrame:
    """Lignes du cache encore fraîches (≤ max_age_days), indexées par ticker."""
    cols = ",".join(["ticker"] + FUND_COLS)
    rows = conn.execute(
        f"select {cols} from fundamentals_cache "
        f"where fetched_at > now() - make_interval(days => %s)", (max_age_days,)
    ).fetchall()
    df = pd.DataFrame(rows, columns=["ticker"] + FUND_COLS)
    return df.set_index("ticker") if not df.empty else df


def get_previous_signals(conn, before_date) -> pd.DataFrame:
    """Signaux du run le plus récent strictement avant `before_date` (pour le delta)."""
    rows = conn.execute(
        "select ticker,signal,trigger from signals where as_of = "
        "(select max(as_of) from signals where as_of < %s)", (before_date,)
    ).fetchall()
    df = pd.DataFrame(rows, columns=["ticker", "signal", "trigger"])
    return df.set_index("ticker") if not df.empty else df


SCORE_COLS = ["quality_z", "quality_pct", "value_xs_z", "combined_z", "drawdown_756",
              "rsi_14", "interest_coverage", "net_debt_ebitda", "fcf_ni",
              "gate_pass", "distress_pass"]


def write_scores(conn, as_of, df: pd.DataFrame) -> None:
    cols = ",".join(SCORE_COLS)
    placeholders = ",".join(f"%({c})s" for c in SCORE_COLS)
    updates = ",".join(f"{c}=excluded.{c}" for c in SCORE_COLS)
    sql = (f"insert into scores (ticker,as_of,{cols}) "
           f"values (%(ticker)s,%(as_of)s,{placeholders}) "
           f"on conflict (ticker,as_of) do update set {updates}")
    payload = [{"ticker": tk, "as_of": as_of,
                **{c: _clean(df.loc[tk, c]) if c in df.columns else None for c in SCORE_COLS}}
               for tk in df.index]
    with conn.cursor() as cur:
        cur.executemany(sql, payload)


def write_signals(conn, as_of, df: pd.DataFrame) -> None:
    sql = ("insert into signals (ticker,as_of,signal,trigger) "
           "values (%(ticker)s,%(as_of)s,%(signal)s,%(trigger)s) "
           "on conflict (ticker,as_of) do update set signal=excluded.signal, trigger=excluded.trigger")
    payload = [{"ticker": tk, "as_of": as_of,
                "signal": _clean(df.loc[tk, "signal"]), "trigger": _clean(df.loc[tk, "trigger"])}
               for tk in df.index]
    with conn.cursor() as cur:
        cur.executemany(sql, payload)


def get_positions(conn, user_id=None) -> pd.DataFrame:
    """Source de vérité (prix d'achat). user_id=None → toutes (job backend)."""
    base = "select ticker,quantity,buy_price,buy_date,user_id from positions"
    if user_id is None:
        rows = conn.execute(base).fetchall()
    else:
        rows = conn.execute(base + " where user_id=%s", (user_id,)).fetchall()
    cols = ["ticker", "quantity", "buy_price", "buy_date", "user_id"]
    return pd.DataFrame(rows, columns=cols)


def start_run(conn, as_of, config_hash_value, universe_count) -> str:
    row = conn.execute(
        "insert into runs (as_of,status,config_hash,universe_count) "
        "values (%s,'running',%s,%s) returning run_id",
        (as_of, config_hash_value, universe_count),
    ).fetchone()
    return str(row[0])


def finish_run(conn, run_id, status, fetched_count, dropped: dict) -> None:
    conn.execute(
        "update runs set finished_at=now(), status=%s, fetched_count=%s, "
        "dropped_count=%s, dropped_detail=%s where run_id=%s",
        (status, fetched_count, len(dropped), json.dumps(dropped), run_id),
    )
