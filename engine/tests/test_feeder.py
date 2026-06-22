"""
Feeder : assemblage du DataFrame-contrat (plusieurs noms) + série de prix.
Transforms pures, testées contre la fixture réelle + données synthétiques.
"""
import json
import pathlib

import pandas as pd

from qv.data.feeder import fundamentals_frame, price_series

FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "fmp_sample_AAPL.json"
CONV = dict(fin_structure_keywords=("Bank", "Insurance"),
            tax_default=0.25, tax_min=0.0, tax_max=0.6, interest_coverage_cap=100.0)


def _synthetic_bundle():
    inc = [{"fiscalYear": "2025", "revenue": 100.0, "grossProfit": 40.0, "ebit": 20.0,
            "ebitda": 25.0, "netIncome": 10.0, "incomeBeforeTax": 15.0,
            "incomeTaxExpense": 3.0, "interestExpense": 5.0}]
    bal = [{"fiscalYear": "2025", "totalDebt": 50.0, "totalStockholdersEquity": 80.0,
            "minorityInterest": 0.0, "cashAndCashEquivalents": 10.0, "netDebt": 40.0,
            "ebitda": 25.0}]
    cf = [{"fiscalYear": "2025", "freeCashFlow": 8.0, "netIncome": 10.0}]
    return {"profile": [{"sector": "Industrials", "industry": "Machinery",
                         "currency": "USD", "marketCap": 500.0}],
            "income": inc, "balance": bal, "cashflow": cf,
            "quote": [{"marketCap": 500.0, "price": 5.0}]}


def test_fundamentals_frame_assembles_rows_per_ticker():
    bundles = {"AAPL": json.loads(FIX.read_text(encoding="utf-8")), "SYN": _synthetic_bundle()}
    df = fundamentals_frame(bundles, conv=CONV)
    assert list(df.index) == ["AAPL", "SYN"]
    assert df.loc["AAPL", "sector"] == "Technology"
    assert df.loc["SYN", "sector"] == "Industrials"
    for col in ("roic_5y_avg", "fcf_5y", "interest_coverage", "nonscore", "years_available"):
        assert col in df.columns


def test_price_series_sorted_ascending_from_newest_first():
    # FMP renvoie newest-first : on doit ressortir une série triée croissante.
    historical = [
        {"date": "2024-01-03", "close": 12.0},
        {"date": "2024-01-02", "close": 11.0},
        {"date": "2024-01-01", "close": 10.0},
    ]
    s = price_series(historical)
    assert list(s.index) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02"),
                             pd.Timestamp("2024-01-03")]
    assert list(s.values) == [10.0, 11.0, 12.0]


def test_price_series_empty_is_empty():
    assert price_series([]).empty
