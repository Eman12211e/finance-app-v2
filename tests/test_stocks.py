import pytest

import config
from services import finnhub_client, fmp_client
from services.market_data import first_two_sentences

SNAPSHOT_KEYS = {"ticker", "name", "is_etf", "exchange", "currency", "sector", "description",
                 "price", "change_percent", "market_cap", "dividend_yield", "expense_ratio"}
VALUE_FIELDS = ("price", "change_percent", "market_cap", "dividend_yield", "expense_ratio")


@pytest.mark.parametrize("ticker", config.DEMO_TICKERS)
def test_demo_snapshot_contract(client, ticker):
    body = client.get(f"/api/stocks/{ticker}/snapshot").get_json()
    assert body["ok"] is True and body["source"] == "demo" and body["error"] is None
    assert body["as_of"]
    data = body["data"]
    assert set(data) == SNAPSHOT_KEYS
    assert data["ticker"] == ticker
    for key in VALUE_FIELDS:
        assert set(data[key]) == {"value", "display"}
        if data[key]["value"] is None:
            assert data[key]["display"] == "Data not available"
    if not data["is_etf"]:
        assert data["expense_ratio"] == {"value": None, "display": "Data not available"}


def test_lowercase_ticker(client):
    body = client.get("/api/stocks/aapl/snapshot").get_json()
    assert body["ok"] is True and body["data"]["ticker"] == "AAPL"


def test_invalid_ticker(client):
    resp = client.get("/api/stocks/AA1/snapshot")
    assert resp.status_code == 400 and resp.get_json()["error"]["code"] == "INVALID_TICKER"


def test_unknown_ticker_demo_mode(client):
    resp = client.get("/api/stocks/ZZZZ/snapshot")
    body = resp.get_json()
    assert resp.status_code == 404 and body["error"]["code"] == "DATA_NOT_AVAILABLE"
    assert body["error"]["message"] == "No data is available for ZZZZ."


def test_demo_origin_never_reported_as_cache(client):
    first = client.get("/api/stocks/KO/snapshot").get_json()
    second = client.get("/api/stocks/KO/snapshot").get_json()
    assert first["source"] == second["source"] == "demo"
    assert first["as_of"] == second["as_of"]


def test_live_then_cache(client, monkeypatch):
    monkeypatch.setattr(config, "DATA_MODE", "live")
    monkeypatch.setattr(finnhub_client, "get_quote", lambda t: {"c": 10.0, "dp": 1.5})
    monkeypatch.setattr(finnhub_client, "get_profile",
                        lambda t: {"name": "Example Corp", "exchange": "NASDAQ", "currency": "USD",
                                   "finnhubIndustry": "Technology", "marketCapitalization": 2500})
    monkeypatch.setattr(fmp_client, "get_profile", lambda t: [{"description": "Example Corp makes widgets."}])
    first = client.get("/api/stocks/AAPL/snapshot").get_json()
    second = client.get("/api/stocks/AAPL/snapshot").get_json()
    assert first["source"] == "live"
    assert second["source"] == "cache" and second["as_of"] == first["as_of"]
    assert first["data"]["market_cap"]["value"] == 2.5e9  # millions -> dollars
    assert first["data"]["dividend_yield"]["display"] == "Data not available"


def test_description_truncation():
    text = "Example Inc. makes widgets. It sells them. It has staff."
    assert first_two_sentences(text) == "Example Inc. makes widgets. It sells them."
    assert first_two_sentences(None) is None
    assert first_two_sentences("One sentence only.") == "One sentence only."
