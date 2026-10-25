"""Call each planned provider endpoint once and report OK / FAIL / SKIP. Never prints key values."""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config  # noqa: E402

FINNHUB = "https://finnhub.io/api/v1"
FMP = "https://financialmodelingprep.com/stable"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "endpoint_check.json")


def endpoints():
    today = date.today()
    later = today + timedelta(days=120)
    return [
        ("finnhub", "quote", f"{FINNHUB}/quote?symbol=AAPL&token={{key}}"),
        ("finnhub", "profile2", f"{FINNHUB}/stock/profile2?symbol=AAPL&token={{key}}"),
        ("finnhub", "earnings", f"{FINNHUB}/stock/earnings?symbol=AAPL&token={{key}}"),
        ("finnhub", "calendar_earnings",
         f"{FINNHUB}/calendar/earnings?symbol=AAPL&from={today}&to={later}&token={{key}}"),
        ("fmp", "profile", f"{FMP}/profile?symbol=AAPL&apikey={{key}}"),
        ("fmp", "profile_etf", f"{FMP}/profile?symbol=VOO&apikey={{key}}"),
        ("fmp", "income_statement_q", f"{FMP}/income-statement?symbol=AAPL&period=quarter&limit=5&apikey={{key}}"),
        ("fmp", "balance_sheet_q",
         f"{FMP}/balance-sheet-statement?symbol=AAPL&period=quarter&limit=5&apikey={{key}}"),
        ("fmp", "dividends", f"{FMP}/dividends?symbol=AAPL&apikey={{key}}"),
    ]


def redact(text, key):
    return text.replace(key, "REDACTED") if key else text


def has_usable_data(body):
    if isinstance(body, list):
        return len(body) > 0
    if isinstance(body, dict):
        lowered = {k.lower() for k in body}
        if lowered & {"error", "error message"}:
            return False
        # calendar_earnings wraps its list in a dict
        if "earningsCalendar" in body:
            return len(body["earningsCalendar"]) > 0
        return len(body) > 0
    return False


def check(provider, name, url_template, key):
    if not key:
        return {"provider": provider, "endpoint": name, "ok": False, "status": None, "note": "SKIP (no key)"}
    try:
        resp = requests.get(url_template.format(key=key), timeout=8)
    except requests.RequestException as exc:
        return {"provider": provider, "endpoint": name, "ok": False, "status": None,
                "note": redact(f"network error: {type(exc).__name__}", key)}
    try:
        body = resp.json()
    except ValueError:
        body = None
    if resp.status_code == 200 and has_usable_data(body):
        return {"provider": provider, "endpoint": name, "ok": True, "status": 200, "note": "usable data"}

    snippet = redact(resp.text[:200], key)
    plan_words = ("premium", "subscription", "upgrade", "plan", "access")
    if resp.status_code == 404 and provider == "fmp":
        note = "path may have changed, check FMP docs"
    elif resp.status_code in (402, 403) or any(w in resp.text.lower()[:500] for w in plan_words):
        note = "not on free tier"
    else:
        note = f"no usable data: {snippet}"
    return {"provider": provider, "endpoint": name, "ok": False, "status": resp.status_code, "note": note}


def main():
    keys = {"finnhub": config.FINNHUB_API_KEY, "fmp": config.FMP_API_KEY}
    results = [check(p, n, u, keys[p]) for p, n, u in endpoints()]
    for r in results:
        label = "SKIP" if r["note"] == "SKIP (no key)" else ("OK" if r["ok"] else "FAIL")
        print(f"{label:<5} {r['provider']:<8} {r['endpoint']:<20} status={r['status']}  {r['note']}")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "results": results}, f, indent=2)


if __name__ == "__main__":
    main()
