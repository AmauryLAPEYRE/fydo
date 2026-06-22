"""
Règle d'univers (SPEC §4.1) — US large-cap, performance-agnostic.
Filtre de TAILLE (market cap), pas de rendement → zéro cherry-pick. Dédup des
classes multiples (GOOG/GOOGL), top-N par market cap. La règle est en config.
"""
from __future__ import annotations


def _is_fin_structure(industry, keywords) -> bool:
    ind = (industry or "").lower()
    return any(k.lower() in ind for k in keywords)


def build_universe(rows: list[dict], *, target_size: int, exchanges, fin_structure_keywords) -> list[dict]:
    """rows = réponses du company-screener FMP → liste de noms du contrat univers."""
    best_by_company: dict[str, dict] = {}
    for r in rows:
        if r.get("exchangeShortName") not in exchanges:
            continue
        if r.get("isEtf") or r.get("isFund") or not r.get("isActivelyTrading"):
            continue
        company = r.get("companyName") or r.get("symbol")
        mcap = r.get("marketCap") or 0
        incumbent = best_by_company.get(company)
        if incumbent is None or mcap > (incumbent.get("marketCap") or 0):
            best_by_company[company] = r

    top = sorted(best_by_company.values(), key=lambda r: r.get("marketCap") or 0,
                 reverse=True)[:target_size]
    return [{
        "ticker": r["symbol"],
        "name": r.get("companyName"),
        "sector": r.get("sector"),
        "currency": "USD",
        "is_fin_structure": _is_fin_structure(r.get("industry"), fin_structure_keywords),
    } for r in top]
