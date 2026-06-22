"""
Client FMP — transport injecté (sans réseau) : construction d'URL, unwrap des
listes, mapping d'erreur. La vraie vérif end-to-end est le run live.
"""
import urllib.error

import pytest

from qv.data.fmp_client import FMPClient, FMPError


def test_profile_builds_url_with_key_and_unwraps_list():
    calls = []

    def fake(url):
        calls.append(url)
        return [{"sector": "Technology"}]

    client = FMPClient("SECRET", "https://x/stable", transport=fake)
    assert client.profile("AAPL") == {"sector": "Technology"}
    assert "profile?symbol=AAPL" in calls[0]
    assert "apikey=SECRET" in calls[0]


def test_income_statement_url_carries_period_and_limit():
    captured = {}

    def fake(url):
        captured["url"] = url
        return [{}] * 5

    FMPClient("K", "b", transport=fake).income_statement("AAPL", 5)
    assert "income-statement?symbol=AAPL&period=annual&limit=5" in captured["url"]


def test_http_error_becomes_fmperror():
    def fake(url):
        raise urllib.error.HTTPError(url, 402, "Payment Required", None, None)

    with pytest.raises(FMPError):
        FMPClient("K", "b", transport=fake).profile("X")


def test_empty_response_raises_fmperror():
    with pytest.raises(FMPError):
        FMPClient("K", "b", transport=lambda u: []).profile("X")
