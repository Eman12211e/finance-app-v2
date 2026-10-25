# Owner: Agent D. Simulated alerts built only from demo_stocks.json, in every DATA_MODE (API_CONTRACT §3.5).
import logging

from services import market_data
from services.formatting import date_display, money_per_share

log = logging.getLogger(__name__)
LABEL = "Simulated alert: demo only"


def _alert(ticker, kind, title, body, event_date):
    return {
        "id": f"{ticker}-{kind}-{event_date}",
        "ticker": ticker,
        "type": kind,
        "title": title,
        "body": body,
        "event_date": event_date,
        "simulated": True,
        "label": LABEL,
    }


def build_alerts(tickers: list[str]) -> list[dict]:
    demo = market_data.load_demo()["tickers"]
    alerts = []
    for ticker in tickers:
        entry = demo.get(ticker)
        if entry is None:
            log.info("alerts: ticker=%s not in demo data, skipped", ticker)
            continue
        name = entry["snapshot"].get("name") or ticker
        fin = entry["financials"]
        div = fin.get("dividend") or {}
        amount, ex_date = div.get("last_amount"), div.get("last_ex_date")
        if div.get("pays_dividend") is True and amount is not None and ex_date:
            alerts.append(_alert(ticker, "dividend", "Dividend paid",
                                 f"{name} paid a dividend of {money_per_share(amount)} per share. "
                                 f"The ex-dividend date was {date_display(ex_date)}.", ex_date))
        next_date = fin.get("next_earnings_date")
        if next_date:
            alerts.append(_alert(ticker, "earnings", "Earnings report expected",
                                 f"{name} is expected to report earnings on {date_display(next_date)}.", next_date))
    return sorted(alerts, key=lambda a: a["event_date"], reverse=True)
