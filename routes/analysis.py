# Analysis Toolbox endpoint (P4). Educational chart data for a verified practice session: bars and preset indicators
# up to the current simulated day only. Read-only: it never changes the session, balances, orders or fills.
import logging

from flask import Blueprint, request
from werkzeug.exceptions import RequestEntityTooLarge

from routes.envelope import fail, ok
from services import explain, indicators, paper_engine, paper_market
from services.errors import AppError, InvalidRequest, RequestTooLarge

log = logging.getLogger(__name__)
bp = Blueprint("analysis", __name__, url_prefix="/api/analysis")

OVERLAYS, PANES = ("sma", "ema"), ("rsi", "macd")
EDUCATION_NOTE = ("Indicator values describe past simulated prices. They are for learning only and are not a "
                  "recommendation to buy or sell.")


def _body():
    try:
        body = request.get_json(silent=True)
    except RequestEntityTooLarge:
        raise RequestTooLarge() from None
    if not isinstance(body, dict):
        raise InvalidRequest()
    return body


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_indicators(raw):
    """[{type, period}] -> [(type, period)] using only the offered presets and the chart limits."""
    if not isinstance(raw, list) or len(raw) > len(OVERLAYS) + len(PANES):
        raise InvalidRequest("Choose up to four indicators from the offered presets.")
    chosen = []
    for item in raw:
        if (not isinstance(item, dict) or set(item) != {"type", "period"} or not isinstance(item["type"], str)
                or item["type"] not in indicators.PRESETS):
            raise InvalidRequest("Choose indicators from the offered presets: SMA, EMA, RSI and MACD.")
        kind, period = item["type"], item["period"]
        if kind == "macd" and isinstance(period, list) and len(period) == 3 and all(_is_int(p) for p in period):
            period = tuple(period)
        if not (_is_int(period) or isinstance(period, tuple)) or period not in indicators.PRESETS[kind]:
            raise InvalidRequest(f"That {kind.upper()} period is not offered.")
        if (kind, period) in chosen:
            raise InvalidRequest("Each indicator can be added once.")
        chosen.append((kind, period))
    if sum(kind in OVERLAYS for kind, _ in chosen) > 2:
        raise InvalidRequest("At most two indicators (SMA or EMA) can be drawn on the price.")
    if sum(kind in PANES for kind, _ in chosen) > 2:
        raise InvalidRequest("At most two indicator panes (RSI or MACD) can be shown.")
    return chosen


def indicator_data(body):
    timeframe, symbol = body.get("timeframe"), body.get("symbol")
    if timeframe not in ("daily", "weekly"):
        raise InvalidRequest("Choose a daily or weekly timeframe.")
    chosen = _parse_indicators(body.get("indicators"))
    data = paper_engine.market_bars(body.get("state"))  # verifies the signed session; bars stop at today
    if not isinstance(symbol, str) or symbol not in data["bars"]:
        raise InvalidRequest("That symbol is not part of this practice scenario.")
    dates, daily = data["dates"], data["bars"][symbol]
    # only the scenario's length is read here (no prices), to know whether today is its final day
    final_day = len(dates) - 1 == paper_market.last_day(paper_market.get(body["state"]["scenario"]))
    if timeframe == "daily":
        bars = [{"time": d, **b} for d, b in zip(dates, daily)]
        closed = bars
    else:
        bars = indicators.weekly(dates, daily, final_day)
        closed = indicators.completed(bars)  # never the Partial Week
    closes = [b["c"] for b in closed]
    padding = [None] * (len(bars) - len(closes))  # the Partial Week's entry, always null
    out = []
    for kind, period in chosen:
        values = indicators.raw(kind, period, closes)
        series = {name: v + padding for name, v in indicators.rounded(kind, values).items()}
        sentence = explain.reading(kind, period, values, closed, timeframe, bars[-1].get("status", "complete"),
                                   bars[-1].get("days"))
        out.append({"type": kind, "period": list(period) if isinstance(period, tuple) else period, "series": series,
                    "reading": sentence})
    return {"symbol": symbol, "timeframe": timeframe, "date": dates[-1], "final_day": final_day, "bars": bars,
            "indicators": out, "notice": data["notice"], "education": EDUCATION_NOTE}


@bp.get("/guide")
def guide_endpoint():
    """The approved explanation text (static), so What is this? works for indicators that are switched off."""
    try:
        return ok(explain.guide(), None, None)
    except Exception:
        log.exception("analysis guide failed")
        return fail(AppError())


@bp.post("/indicators")
def indicators_endpoint():
    try:
        return ok(indicator_data(_body()), None, None)
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("analysis request failed")
        return fail(AppError())
