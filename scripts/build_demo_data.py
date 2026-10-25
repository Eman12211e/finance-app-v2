"""Build data/demo_stocks.json from yfinance (offline only). Missing values are null; nothing is estimated."""
import json
import math
import os
import sys
import warnings
from datetime import date, datetime, timezone

import yfinance as yf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config  # noqa: E402

warnings.filterwarnings("ignore")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "demo_stocks.json")


def clean(v):
    """NaN / None / non-numbers -> None; numpy scalars -> plain Python numbers."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def as_percent(reported, expected_pct):
    """Return `reported` as a percent level, checking its unit against an independently computed percent.
    None if the unit cannot be confirmed."""
    reported = clean(reported)
    if reported is None or expected_pct is None:
        return None
    if expected_pct == 0:
        return reported if reported == 0 else None

    def close(a):
        return 0.5 <= a / expected_pct <= 2

    if close(reported):
        return reported
    if close(reported * 100):
        return reported * 100
    return None


def iso(ts):
    return ts.date().isoformat() if hasattr(ts, "date") else str(ts)[:10]


def row_value(df, row, col):
    if df is None or df.empty or row not in df.index or col not in df.columns:
        return None
    return clean(df.at[row, col])


def build_snapshot(ticker, info):
    price = clean(info.get("currentPrice")) or clean(info.get("regularMarketPrice"))
    prev = clean(info.get("regularMarketPreviousClose")) or clean(info.get("previousClose"))
    change_expected = (price / prev - 1) * 100 if price and prev else None
    # dividendYield is forward-looking, so check it against the forward rate first
    rate = clean(info.get("dividendRate")) or clean(info.get("trailingAnnualDividendRate"))
    yield_expected = rate / price * 100 if rate is not None and price else None
    is_etf = info.get("quoteType") == "ETF"
    return {
        "ticker": ticker,
        "name": info.get("longName"),
        "is_etf": is_etf,
        "exchange": info.get("fullExchangeName") or info.get("exchange"),
        "currency": info.get("currency"),
        "sector": info.get("sector"),
        "description_full": info.get("longBusinessSummary"),
        "price": price,
        "change_percent": as_percent(info.get("regularMarketChangePercent"), change_expected),
        # ETFs: totalAssets is not market cap
        "market_cap": None if is_etf else clean(info.get("marketCap")),
        "dividend_yield": as_percent(info.get("dividendYield"), yield_expected),
        # yfinance netExpenseRatio is already a percent level (VOO: 0.03 = 0.03%)
        "expense_ratio": clean(info.get("netExpenseRatio")) if is_etf else None,
    }


def build_quarters(t):
    inc, bal = t.quarterly_income_stmt, t.quarterly_balance_sheet
    cols = sorted(inc.columns, reverse=True)[:5] if inc is not None and not inc.empty else []
    return [
        {
            "period_end": iso(c),
            "revenue": row_value(inc, "Total Revenue", c),
            "net_income": row_value(inc, "Net Income", c),
            "cash_and_equivalents": row_value(bal, "Cash And Cash Equivalents", c),
        }
        for c in cols
    ]


def build_eps(t):
    eh = t.earnings_history
    if eh is None or eh.empty:
        return None
    for quarter in sorted(eh.index, reverse=True):
        actual, estimate = clean(eh.at[quarter, "epsActual"]), clean(eh.at[quarter, "epsEstimate"])
        if actual is not None and estimate is not None:
            # earnings_history has no report date column
            return {"period_end": iso(quarter), "report_date": None, "actual": actual, "estimate": estimate}
    return None


def build_dividend(t):
    try:
        divs = t.dividends
    except Exception:
        return {"pays_dividend": None, "last_amount": None, "last_ex_date": None}
    if divs is None or divs.empty:
        return {"pays_dividend": False, "last_amount": None, "last_ex_date": None}
    return {"pays_dividend": True, "last_amount": clean(divs.iloc[-1]), "last_ex_date": iso(divs.index[-1])}


def next_earnings(t):
    try:
        dates = (t.calendar or {}).get("Earnings Date") or []
    except Exception:
        return None
    future = sorted(d for d in dates if d > date.today())
    return future[0].isoformat() if future else None


def build_ticker(ticker):
    t = yf.Ticker(ticker)
    snapshot = build_snapshot(ticker, t.info)
    etf = snapshot["is_etf"]
    return {
        "snapshot": snapshot,
        "financials": {
            "quarters": [] if etf else build_quarters(t),
            "eps": None if etf else build_eps(t),
            "dividend": build_dividend(t),
            "next_earnings_date": None if etf else next_earnings(t),
        },
    }


def has_prior_year(quarters):
    """Same window as API_CONTRACT §3.3: a quarter 350-380 days before the newest one."""
    if not quarters:
        return False
    newest = date.fromisoformat(quarters[0]["period_end"])
    return any(350 <= (newest - date.fromisoformat(q["period_end"])).days <= 380 for q in quarters[1:])


def gap_table(tickers):
    fields = ["name", "exchange", "sector", "description_full", "price", "change_percent", "market_cap",
              "dividend_yield", "expense_ratio", "quarters", "prior_year_q", "eps", "dividend", "next_earnings"]
    print(f"\n{'field':<17}" + "".join(f"{t:<6}" for t in tickers))
    for f in fields:
        cells = []
        for t in tickers.values():
            s, fin = t["snapshot"], t["financials"]
            if f == "quarters":
                v = len(fin["quarters"]) or None
            elif f == "prior_year_q":
                v = has_prior_year(fin["quarters"]) or None
            elif f == "eps":
                v = fin["eps"]
            elif f == "dividend":
                v = fin["dividend"]["last_amount"]
            elif f == "next_earnings":
                v = fin["next_earnings_date"]
            else:
                v = s[f]
            cells.append("ok" if v is not None else "null")
        print(f"{f:<17}" + "".join(f"{c:<6}" for c in cells))


def main():
    tickers = {t: build_ticker(t) for t in config.DEMO_TICKERS}
    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "yfinance",
        "tickers": tickers,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {os.path.normpath(OUT_PATH)}")
    gap_table(tickers)


if __name__ == "__main__":
    main()
