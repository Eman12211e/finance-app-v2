import copy

from services import market_data
from services.formatting import date_display, money_per_share

LABEL = "Simulated alert: demo only"


def get_alerts(client, query):
    return client.get("/api/alerts" + query)


def test_alerts_are_simulated_and_demo_sourced(client):
    body = get_alerts(client, "?tickers=AAPL,KO").get_json()
    assert body["ok"] is True and body["source"] == "demo"
    assert body["as_of"] == market_data.load_demo()["generated_at"]
    alerts = body["data"]["alerts"]
    assert alerts and {a["ticker"] for a in alerts} == {"AAPL", "KO"}
    for a in alerts:
        assert a["simulated"] is True and a["label"] == LABEL
        assert a["type"] in ("dividend", "earnings")
        assert a["id"] == f"{a['ticker']}-{a['type']}-{a['event_date']}"


def test_ko_dividend_body_comes_from_demo_data(client):
    ko = market_data.load_demo()["tickers"]["KO"]
    div = ko["financials"]["dividend"]
    expected = (f"{ko['snapshot']['name']} paid a dividend of {money_per_share(div['last_amount'])} per share. "
                f"The ex-dividend date was {date_display(div['last_ex_date'])}.")
    alerts = get_alerts(client, "?tickers=KO").get_json()["data"]["alerts"]
    dividend = [a for a in alerts if a["type"] == "dividend"]
    assert len(dividend) == 1 and dividend[0]["body"] == expected and dividend[0]["title"] == "Dividend paid"
    assert dividend[0]["event_date"] == div["last_ex_date"]


def test_earnings_alert_says_expected(client):
    ko = market_data.load_demo()["tickers"]["KO"]
    alerts = get_alerts(client, "?tickers=KO").get_json()["data"]["alerts"]
    earnings = [a for a in alerts if a["type"] == "earnings"]
    assert earnings[0]["body"] == (f"{ko['snapshot']['name']} is expected to report earnings on "
                                   f"{date_display(ko['financials']['next_earnings_date'])}.")
    assert earnings[0]["title"] == "Earnings report expected"


def test_missing_tickers_is_invalid_request(client):
    for query in ("", "?tickers=", "?tickers=,%20,"):
        resp = get_alerts(client, query)
        assert resp.status_code == 400 and resp.get_json()["error"]["code"] == "INVALID_REQUEST"


def test_bad_ticker_format(client):
    resp = get_alerts(client, "?tickers=AA1")
    assert resp.status_code == 400 and resp.get_json()["error"]["code"] == "INVALID_TICKER"


def test_unknown_ticker_skipped(client):
    alerts = get_alerts(client, "?tickers=AAPL,ZZZZ").get_json()["data"]["alerts"]
    assert alerts and all(a["ticker"] == "AAPL" for a in alerts)


def test_null_values_create_no_alert(client, monkeypatch):
    demo = copy.deepcopy(market_data.load_demo())
    demo["tickers"]["EXMPL"] = {  # synthetic, tests only
        "snapshot": {"ticker": "EXMPL", "name": "Example Corp"},
        "financials": {"quarters": [], "eps": None,
                       "dividend": {"pays_dividend": True, "last_amount": 0.25, "last_ex_date": None},
                       "next_earnings_date": None},
    }
    monkeypatch.setattr(market_data, "load_demo", lambda: demo)
    body = get_alerts(client, "?tickers=EXMPL").get_json()
    assert body["ok"] is True and body["data"]["alerts"] == []


def test_sorted_newest_first(client):
    alerts = get_alerts(client, "?tickers=AAPL,MSFT,KO,NVDA,VOO").get_json()["data"]["alerts"]
    dates = [a["event_date"] for a in alerts]
    assert len(dates) > 1 and dates == sorted(dates, reverse=True)
