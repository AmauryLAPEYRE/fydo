"""
Règle d'univers (screener FMP → liste). Performance-agnostic : filtre de TAILLE,
dédup dual-class, top-N par market cap. Aucun cherry-pick de rendement.
"""
from qv.data.screener import build_universe

KW = ("Bank", "Insurance")


def _row(symbol, name, mcap, *, sector="Technology", industry="Software",
         exch="NASDAQ", etf=False, fund=False, active=True):
    return {"symbol": symbol, "companyName": name, "marketCap": mcap, "sector": sector,
            "industry": industry, "exchangeShortName": exch, "isEtf": etf,
            "isFund": fund, "isActivelyTrading": active}


def test_dedup_dual_class_keeps_largest_mcap():
    rows = [_row("GOOGL", "Alphabet Inc.", 100), _row("GOOG", "Alphabet Inc.", 90)]
    out = build_universe(rows, target_size=10, exchanges=("NASDAQ",), fin_structure_keywords=KW)
    assert [u["ticker"] for u in out] == ["GOOGL"]


def test_excludes_etf_fund_inactive_and_other_exchanges():
    rows = [
        _row("OK", "Good Co", 50),
        _row("ETF", "An ETF", 999, etf=True),
        _row("FND", "A Fund", 999, fund=True),
        _row("DEAD", "Inactive", 999, active=False),
        _row("OTC", "Pinksheet", 999, exch="OTC"),
    ]
    out = build_universe(rows, target_size=10, exchanges=("NASDAQ", "NYSE"), fin_structure_keywords=KW)
    assert [u["ticker"] for u in out] == ["OK"]


def test_top_n_by_market_cap():
    rows = [_row(f"T{i}", f"Co {i}", mc) for i, mc in enumerate([10, 50, 30, 90, 20])]
    out = build_universe(rows, target_size=3, exchanges=("NASDAQ",), fin_structure_keywords=KW)
    assert [u["ticker"] for u in out] == ["T3", "T1", "T2"]  # 90, 50, 30


def test_fin_structure_flagged():
    rows = [_row("JPM", "JPMorgan", 100, sector="Financial Services", industry="Banks - Diversified")]
    out = build_universe(rows, target_size=10, exchanges=("NASDAQ", "NYSE"), fin_structure_keywords=KW)
    assert out[0]["is_fin_structure"] is True
