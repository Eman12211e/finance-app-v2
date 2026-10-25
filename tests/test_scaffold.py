import json
import os
from unittest.mock import patch

import pytest

import config
from routes.envelope import fail
from services import cache
from services.errors import InvalidProfile, InvalidTicker
from services.validation import validate_profile, validate_ticker

DEMO_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "demo_stocks.json")


def test_tests_never_see_real_api_keys():
    # conftest.py must blank these before config loads, so pytest can never call paid or live APIs
    assert config.ANTHROPIC_API_KEY == config.FINNHUB_API_KEY == config.FMP_API_KEY == ""
    assert config.DATA_MODE == "demo" and config.WARM_CACHE is False


def test_health_envelope(client):
    resp = client.get("/api/health")
    body = resp.get_json()
    assert resp.status_code == 200
    assert set(body) == {"ok", "data", "source", "as_of", "error"}
    assert body["ok"] is True and body["source"] is None and body["as_of"] is None and body["error"] is None
    assert body["data"]["status"] == "ok"
    assert body["data"]["data_mode"] == "demo"
    keys = body["data"]["keys_present"]
    assert set(keys) == {"anthropic", "finnhub", "fmp"}
    assert all(isinstance(v, bool) for v in keys.values())


def test_index_serves_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    for container in (b'id="disclaimer-footer"', b'id="watchlist-root"', b'id="snapshot-root"',
                      b'id="earnings-root"', b'id="chat-root"'):
        assert container in resp.data


@pytest.mark.parametrize("raw, expected", [("aapl", "AAPL"), (" msft ", "MSFT"), ("BRK.B", "BRK.B")])
def test_validate_ticker_ok(raw, expected):
    assert validate_ticker(raw) == expected


@pytest.mark.parametrize("raw", ["TOOLONG", "AA1", "", None, "BRK.BB"])
def test_validate_ticker_rejects(raw):
    with pytest.raises(InvalidTicker):
        validate_ticker(raw)


def test_validate_profile():
    assert validate_profile("25-34", "medium") == {"age_range": "25-34", "risk": "medium"}
    for age, risk in [("99", "medium"), ("25-34", "extreme"), (None, None)]:
        with pytest.raises(InvalidProfile):
            validate_profile(age, risk)


def test_cache_expires():
    with patch("services.cache.time.time", return_value=1000.0):
        cache.set("k", "v", 1)
        assert cache.get("k") == "v"
    with patch("services.cache.time.time", return_value=1000.5):
        assert cache.get("k") == "v"
    with patch("services.cache.time.time", return_value=1001.0):
        assert cache.get("k") is None


def test_demo_data_shape():
    with open(DEMO_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert data["generated_at"] and data["generator"] == "yfinance"
    assert set(data["tickers"]) == set(config.DEMO_TICKERS)
    for entry in data["tickers"].values():
        assert "snapshot" in entry and "financials" in entry
    voo = data["tickers"]["VOO"]
    assert voo["snapshot"]["is_etf"] is True
    assert voo["financials"]["quarters"] == []
    assert voo["financials"]["eps"] is None


def test_fail_envelope(client):
    with client.application.app_context():
        resp, status = fail(InvalidTicker())
    body = resp.get_json()
    assert status == 400
    assert body == {
        "ok": False, "data": None, "source": None, "as_of": None,
        "error": {"code": "INVALID_TICKER", "message": InvalidTicker.default_message},
    }
