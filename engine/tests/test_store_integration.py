"""
Intégration store ↔ Supabase réel. Marqué `slow` (hors suite rapide), skip si pas
de DATABASE_URL. Round-trip sur un ticker de test, nettoyé après.
"""
import datetime
import pathlib

import pandas as pd
import pytest

pytestmark = pytest.mark.slow

from qv.data import store  # noqa: E402

TEST_TICKER = "ZZTEST"
TEST_DATE = datetime.date(2000, 1, 1)


def _database_url():
    env = pathlib.Path(__file__).resolve().parents[2] / ".env"
    if not env.exists():
        return None
    for line in env.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    return None


@pytest.fixture
def conn():
    url = _database_url()
    if not url:
        pytest.skip("DATABASE_URL absent")
    c = store.get_connection(url)
    yield c
    # cleanup
    for t in ("scores", "signals"):
        c.execute(f"delete from {t} where ticker=%s", (TEST_TICKER,))
    c.execute("delete from universe where ticker=%s", (TEST_TICKER,))
    c.execute("delete from runs where config_hash=%s", ("ZZTEST_HASH",))
    c.close()


def test_universe_roundtrip(conn):
    store.upsert_universe(conn, [{"ticker": TEST_TICKER, "name": "Test", "sector": "Tech",
                                  "currency": "USD", "is_fin_structure": False}],
                          screen_rule="test-rule", screened_at=TEST_DATE)
    row = conn.execute("select sector,is_fin_structure from universe where ticker=%s",
                       (TEST_TICKER,)).fetchone()
    assert row == ("Tech", False)


def test_scores_and_signals_roundtrip(conn):
    df = pd.DataFrame(
        {"quality_z": [1.23], "value_xs_z": [0.45], "combined_z": [0.84],
         "gate_pass": [True], "distress_pass": [True], "signal": ["ACCUMULER"],
         "trigger": ["entry_ok"]},
        index=[TEST_TICKER],
    )
    store.write_scores(conn, TEST_DATE, df)
    store.write_signals(conn, TEST_DATE, df)
    sc = conn.execute("select combined_z,gate_pass from scores where ticker=%s and as_of=%s",
                      (TEST_TICKER, TEST_DATE)).fetchone()
    sg = conn.execute("select signal,trigger from signals where ticker=%s and as_of=%s",
                      (TEST_TICKER, TEST_DATE)).fetchone()
    assert sc == (0.84, True)
    assert sg == ("ACCUMULER", "entry_ok")


def test_run_lifecycle_and_positions(conn):
    run_id = store.start_run(conn, TEST_DATE, "ZZTEST_HASH", 1)
    store.finish_run(conn, run_id, "ok", 1, {"DROPME": "HTTP 402"})
    row = conn.execute("select status,dropped_count,dropped_detail from runs where run_id=%s",
                       (run_id,)).fetchone()
    assert row[0] == "ok" and row[1] == 1 and row[2] == {"DROPME": "HTTP 402"}
    # positions : DataFrame valide (vide tant qu'aucun user n'a saisi)
    pos = store.get_positions(conn)
    assert list(pos.columns) == ["ticker", "quantity", "buy_price", "buy_date", "user_id"]
