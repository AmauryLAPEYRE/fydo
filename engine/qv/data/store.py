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


def upsert_universe(conn, rows: list[dict]) -> None:
    sql = """insert into universe (ticker,name,sector,currency,is_fin_structure,active)
             values (%(ticker)s,%(name)s,%(sector)s,%(currency)s,%(is_fin_structure)s,%(active)s)
             on conflict (ticker) do update set
               name=excluded.name, sector=excluded.sector, currency=excluded.currency,
               is_fin_structure=excluded.is_fin_structure, active=excluded.active"""
    with conn.cursor() as cur:
        cur.executemany(sql, [{k: _clean(v) for k, v in r.items()} for r in rows])


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
