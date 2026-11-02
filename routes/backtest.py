# Test a strategy endpoint (P5). Replays a preset rule and buy-and-hold on one ticker of a verified practice session,
# up to the current simulated day only. Read-only: it never changes the session, balances, orders or fills.
import logging

from flask import Blueprint, request
from werkzeug.exceptions import RequestEntityTooLarge

from routes.envelope import fail, ok
from services import backtest, indicators, paper_engine
from services.errors import AppError, InvalidRequest, RequestTooLarge

log = logging.getLogger(__name__)
bp = Blueprint("backtest", __name__, url_prefix="/api/backtest")

FIELDS = ("state", "symbol", "preset", "costs")
CHART_LINES = {"sma_cross": (("sma", backtest.FAST), ("sma", backtest.SLOW)), "rsi_threshold": (("rsi", 14),)}
STANDING_NOTE = ("This is a hypothetical test on computer-generated prices. A rule that did well here can do badly on "
                 "other prices. Past results, real or simulated, do not tell you what will happen next.")


def _body():
    try:
        body = request.get_json(silent=True)
    except RequestEntityTooLarge:
        raise RequestTooLarge() from None
    if not isinstance(body, dict):
        raise InvalidRequest()
    return body


def _window(sim):
    first, last = sim["values"][0], sim["values"][-1]
    return {"start_index": first["index"], "start_date": first["date"], "last_index": last["index"],
            "last_date": last["date"], "evaluation_days": last["index"] - first["index"]}


def _side(sim, with_values=True):
    end = sim["values"][-1]
    out = {"metrics": sim["metrics"], "fills": sim["fills"], "skipped": sim["skipped"],
           "end": {"cash_cents": end["cash_cents"], "shares": end["shares"], "close_cents": end["close_cents"]}}
    if with_values:
        out["values"] = [{"time": v["date"], "value_cents": v["value_cents"]} for v in sim["values"]]
    return out


def _comparison(c, with_values=True):
    return {"window": _window(c["strategy"]), "strategy": _side(c["strategy"], with_values),
            "benchmark": _side(c["benchmark"], with_values), "difference_pp": c["difference_pp"],
            "unacted_signal": c["strategy"]["unacted_signal"]}


def run_data(body):
    if any(k not in FIELDS for k in body):
        raise InvalidRequest("Send only state, symbol, preset and costs.")
    preset, costs, symbol = body.get("preset"), body.get("costs"), body.get("symbol")
    if not isinstance(preset, str) or preset not in backtest.RULES:
        raise InvalidRequest("Choose a rule: sma_cross or rsi_threshold.")
    if not isinstance(costs, str) or costs not in backtest.SLIPPAGE_BPS:
        raise InvalidRequest("Choose a cost setting: example or none.")
    data = paper_engine.market_bars(body.get("state"))  # verifies the signed session; bars stop at today
    if not isinstance(symbol, str) or symbol not in data["bars"]:
        raise InvalidRequest("That symbol is not part of this practice scenario.")
    dates, bars = data["dates"], data["bars"][symbol]
    out = {"symbol": symbol, "preset": preset, "costs": costs, "date": dates[-1],
           "needed_days": backtest.NEEDED_DAYS, "available_days": len(bars), "window": None, "result": None,
           "notice": data["notice"], "education": STANDING_NOTE}
    run = backtest.run(dates, bars, preset, costs)["result"]
    if run is None:
        return out
    closes = [b["c"] for b in bars]
    halves = run["halves"] and {
        "midpoint_index": run["halves"]["midpoint_index"], "midpoint_date": dates[run["halves"]["midpoint_index"]],
        "earlier": _comparison(run["halves"]["earlier"], False), "later": _comparison(run["halves"]["later"], False)}
    result = _comparison(run) | {
        "halves": halves, "dates": dates,
        "bars": [{"time": d, "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"]} for d, b in zip(dates, bars)],
        "indicators": [{"type": kind, "period": n, "series": indicators.compute(kind, n, closes)}
                       for kind, n in CHART_LINES[preset]]}
    return out | {"window": result.pop("window"), "result": result}


@bp.post("/run")
def run_endpoint():
    try:
        return ok(run_data(_body()), None, None)
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("backtest request failed")
        return fail(AppError())
