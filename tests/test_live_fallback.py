"""Agent E: live-mode behaviour with every provider mocked. No real network calls (requests.get is blocked)."""
import logging

import pytest
import requests

import config
from services import finnhub_client, fmp_client, market_data, warmup
from services.errors import ProviderError

URL = "/api/stocks/{}/{}"
EARNINGS_Q = "?age_range=25-34&risk=medium"


def fail(*_):
    raise ProviderError()


class CallLog(list):
    install = None  # set by the fixture: swap one provider call's result


@pytest.fixture
def live(monkeypatch):
    """Live mode with every provider call mocked (fake numbers, tests only). Returns the call log."""
    def no_network(*a, **k):
        raise AssertionError("real network call attempted in a test")
    monkeypatch.setattr(requests, "get", no_network)
    monkeypatch.setattr(config, "DATA_MODE", "live")
    monkeypatch.setattr(market_data, "_failed_endpoints", set())
    calls = CallLog()
    fakes = {
        (finnhub_client, "get_quote"): {"c": 10.0, "dp": 1.5},
        (finnhub_client, "get_profile"): {"name": "Example Corp", "exchange": "NASDAQ", "currency": "USD",
                                          "finnhubIndustry": "Technology", "marketCapitalization": 2500},
        (finnhub_client, "get_earnings"): [{"period": "2026-06-30", "actual": 1.23, "estimate": 1.20}],
        (finnhub_client, "get_earnings_calendar"): {"earningsCalendar": [{"date": "2099-01-30"}]},
        (fmp_client, "get_profile"): [{"description": "Example Corp makes widgets. It sells them.", "isEtf": False}],
        (fmp_client, "get_income_statement_quarterly"): [
            {"date": "2026-06-27", "revenue": 1.06e10, "netIncome": 2.0e9},
            {"date": "2025-06-28", "revenue": 1.0e10, "netIncome": 1.8e9}],
        (fmp_client, "get_balance_sheet_quarterly"): [{"date": "2026-06-27", "cashAndCashEquivalents": 3.0e10}],
        (fmp_client, "get_dividends"): [{"date": "2026-08-10", "dividend": 0.25}],
    }

    def install(module, name, result):
        def fake(t):
            calls.append(name if module is finnhub_client else "fmp." + name)
            if callable(result):
                return result(t)
            return result
        monkeypatch.setattr(module, name, fake)

    for (module, name), result in fakes.items():
        install(module, name, result)
    calls.install = install  # lets a test swap one provider call for a failure
    return calls


def get(client, ticker, part, query=""):
    return client.get(URL.format(ticker, part) + query)


def test_quote_failure_falls_back_to_demo_snapshot(client, live):
    live.install(finnhub_client, "get_quote", fail)
    body = get(client, "AAPL", "snapshot").get_json()
    demo = market_data.load_demo()
    assert body["ok"] is True and body["source"] == "demo" and body["as_of"] == demo["generated_at"]
    assert body["data"]["name"] == demo["tickers"]["AAPL"]["snapshot"]["name"]


def test_income_failure_falls_back_to_demo_financials(client, live):
    live.install(fmp_client, "get_income_statement_quarterly", fail)
    body = get(client, "AAPL", "earnings", EARNINGS_Q).get_json()
    assert body["ok"] is True and body["source"] == "demo"
    assert body["data"]["sections"]["eps"]["source_label"] == "Analyst average estimate (source: demo data)"


def test_single_noncritical_failure_is_null_not_fallback(client, live):
    live.install(fmp_client, "get_dividends", fail)
    body = get(client, "AAPL", "earnings", EARNINGS_Q).get_json()
    div = body["data"]["sections"]["dividend"]
    assert body["source"] == "live"
    assert div["pays_dividend"] is None and div["last_amount"]["display"] == "Data not available"
    assert body["data"]["sections"]["revenue"]["value"]["value"] == 1.06e10  # the live figure, not demo
    assert body["data"]["sections"]["eps"]["source_label"] == "Analyst average estimate (source: Finnhub)"


def test_unknown_ticker_and_failed_quote_is_404(client, live):
    live.install(finnhub_client, "get_quote", fail)
    resp = get(client, "ZZZZ", "snapshot")
    assert resp.status_code == 404 and resp.get_json()["error"]["code"] == "DATA_NOT_AVAILABLE"


def test_live_then_cache_keeps_as_of_and_finnhub_label(client, live):
    first = get(client, "AAPL", "earnings", EARNINGS_Q).get_json()
    n_calls = len(live)
    second = get(client, "AAPL", "earnings", EARNINGS_Q).get_json()
    assert first["source"] == "live" and second["source"] == "cache"
    assert second["as_of"] == first["as_of"]
    assert second["data"]["sections"]["eps"]["source_label"] == "Analyst average estimate (source: Finnhub)"
    assert len(live) == n_calls  # reload within TTL makes zero provider calls


def test_demo_fallback_is_never_reported_as_cache(client, live):
    live.install(finnhub_client, "get_quote", fail)
    first = get(client, "KO", "snapshot").get_json()
    second = get(client, "KO", "snapshot").get_json()
    assert first["source"] == second["source"] == "demo"


def test_market_cap_millions_converted(client, live):
    data = get(client, "AAPL", "snapshot").get_json()["data"]
    assert data["market_cap"]["value"] == 2.5e9


def test_live_snapshot_never_borrows_demo_values(client, live):
    body = get(client, "KO", "snapshot").get_json()
    assert body["source"] == "live" and market_data.load_demo()["tickers"]["KO"]["snapshot"]["dividend_yield"] is not None
    assert body["data"]["dividend_yield"] == {"value": None, "display": "Data not available"}  # no reliable live source
    assert body["data"]["expense_ratio"] == {"value": None, "display": "Data not available"}


def test_future_declared_dividend_is_not_last_paid(client, live):
    live.install(fmp_client, "get_dividends", [{"date": "2026-08-10", "dividend": 0.25},
                                               {"date": "2099-11-20", "dividend": 0.30}])
    div = get(client, "AAPL", "earnings", EARNINGS_Q).get_json()["data"]["sections"]["dividend"]
    assert div["last_amount"]["value"] == 0.25 and div["last_ex_date"] == "2026-08-10"


def test_failed_endpoint_is_never_called(client, live, monkeypatch):
    monkeypatch.setattr(market_data, "_failed_endpoints", {("fmp", "dividends")})
    body = get(client, "AAPL", "earnings", EARNINGS_Q).get_json()
    assert "fmp.get_dividends" not in live
    assert body["source"] == "live" and body["data"]["sections"]["dividend"]["pays_dividend"] is None


def test_provider_calls_are_counted_in_the_log(client, live, caplog):
    with caplog.at_level(logging.INFO, logger="services.market_data"):
        get(client, "AAPL", "earnings", EARNINGS_Q)
    lines = [r.getMessage() for r in caplog.records if " call #" in r.getMessage()]
    assert any(l.startswith("fmp call #") and "endpoint=income_statement_q ticker=AAPL" in l for l in lines)
    assert sum(l.startswith("fmp call") for l in lines) <= 4  # PROMPT_E §2.4: at most 4 FMP calls per stock


def test_etf_flag_from_fmp_profile_skips_income_statement(client, live):
    live.install(fmp_client, "get_profile", [{"description": "A fund.", "isEtf": True}])
    body = get(client, "SPY", "earnings", EARNINGS_Q).get_json()
    assert body["source"] == "live" and body["data"]["is_etf"] is True
    assert "fmp.get_income_statement_quarterly" not in live


def test_warmup_disabled_logs(caplog, monkeypatch):
    monkeypatch.setattr(config, "WARM_CACHE", False)
    with caplog.at_level(logging.INFO, logger="services.warmup"):
        warmup.run_if_enabled(None)
    assert "warmup disabled" in caplog.text


def test_warmup_loads_every_ticker_in_demo_mode(caplog):
    with caplog.at_level(logging.INFO, logger="services.warmup"):
        warmup._warm()
    assert f"warmup done: {len(config.DEMO_TICKERS)}/{len(config.DEMO_TICKERS)} tickers" in caplog.text
    for t in config.DEMO_TICKERS:
        assert market_data.get_snapshot(t)[1] == "demo"  # still labelled demo after warming
