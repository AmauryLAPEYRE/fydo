"""
Client FMP (API stable). Transport injectable → testable sans réseau.
Clé en paramètre (jamais en dur). Erreurs HTTP → FMPError explicite (fail-neutral
géré par l'appelant : un nom qui échoue est droppé et loggé, pas un faux signal).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


class FMPError(Exception):
    """Échec d'un appel FMP (HTTP non-200, premium, rate-limit…)."""


def _http_get(url: str):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


class FMPClient:
    def __init__(self, api_key: str, base_url: str, transport=_http_get, pause: float = 0.0):
        self._key = api_key
        self._base = base_url.rstrip("/")
        self._transport = transport
        self._pause = pause

    def _get(self, path: str):
        sep = "&" if "?" in path else "?"
        url = f"{self._base}/{path}{sep}apikey={self._key}"
        try:
            data = self._transport(url)
        except urllib.error.HTTPError as e:
            raise FMPError(f"HTTP {e.code} sur {path.split('?')[0]}") from e
        except urllib.error.URLError as e:
            raise FMPError(f"réseau sur {path.split('?')[0]}: {e.reason}") from e
        if self._pause:
            time.sleep(self._pause)
        return data

    @staticmethod
    def _first(data):
        if not isinstance(data, list) or not data:
            raise FMPError("réponse vide / inattendue")
        return data[0]

    def profile(self, symbol: str) -> dict:
        return self._first(self._get(f"profile?symbol={symbol}"))

    def quote(self, symbol: str) -> dict:
        return self._first(self._get(f"quote?symbol={symbol}"))

    def income_statement(self, symbol: str, years: int) -> list:
        return self._get(f"income-statement?symbol={symbol}&period=annual&limit={years}")

    def balance_sheet(self, symbol: str, years: int) -> list:
        return self._get(f"balance-sheet-statement?symbol={symbol}&period=annual&limit={years}")

    def cash_flow(self, symbol: str, years: int) -> list:
        return self._get(f"cash-flow-statement?symbol={symbol}&period=annual&limit={years}")

    def historical_prices(self, symbol: str, start: str) -> list:
        """EOD daily depuis `start` (YYYY-MM-DD). FMP renvoie newest-first."""
        return self._get(f"historical-price-eod/full?symbol={symbol}&from={start}")

    def fundamentals_bundle(self, symbol: str, years: int) -> dict:
        """Les 5 réponses attendues par derive_fundamentals (1 nom)."""
        return {
            "profile": [self.profile(symbol)],
            "income": self.income_statement(symbol, years),
            "balance": self.balance_sheet(symbol, years),
            "cashflow": self.cash_flow(symbol, years),
            "quote": [self.quote(symbol)],
        }
