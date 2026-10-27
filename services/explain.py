"""Current-reading sentences for the Analysis Toolbox (P4 step 6), from the approved text in data/indicator_guide.json.

Each sentence is chosen from unrounded indicator values (services.indicators.raw); numbers are rounded only for
display, and a displayed number gets extra decimals when the usual rounding would contradict the chosen sentence
(RSI 69.996 shows as "69.996", not "70.0", in a "between 30 and 70" sentence). Static text only: no AI, no network."""
import json
import os

GUIDE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "indicator_guide.json")
_guide = None


def guide():
    global _guide
    if _guide is None:
        with open(GUIDE_PATH, encoding="utf-8") as f:
            _guide = json.load(f)
    return _guide


def shown(value, digits, keeps):
    """value with `digits` decimals, or more (up to 6) while the rounded number would break keeps(rounded)."""
    for d in range(digits, 7):
        text = f"{value:.{d}f}"
        if text.startswith("-") and float(text) == 0:
            text = text[1:]  # never "-0.00"
        if keeps(float(text)):
            break
    return text


def _side(value):
    return "above" if value > 0 else "below" if value < 0 else "at"


def _compare(a, b):
    return "above" if a > b else "below" if a < b else "level"


def _rsi_zone(v):
    return "high" if v >= 70 else "low" if v <= 30 else "middle" if v == 50 else "upper" if v > 50 else "lower"


def name_of(kind, period):
    return kind.upper() + " " + ("-".join(str(p) for p in period) if isinstance(period, tuple) else str(period))


def reading(kind, period, values, closed_bars, timeframe, last_status="complete", last_days=None):
    """The current-reading sentence for one indicator.

    values: raw() output, aligned with closed_bars (the bars the indicator was calculated from: every daily bar, or
    the completed weeks). last_status / last_days describe the chart's last bar ("partial" and "final_short" add the
    approved weekly sentences)."""
    g, shared = guide(), guide()["shared"]
    text = g["indicators"][kind]["readings"]
    unit, units = shared["unit"][timeframe], shared["units"][timeframe]
    at = len(closed_bars) - 1  # the last completed bar
    parts = [shared["weekly_prefix"]] if timeframe == "weekly" else []

    def missing(needed, name=None):
        return shared["not_enough"].format(name=name or name_of(kind, period), needed=needed, units=units,
                                           have=len(closed_bars))

    if kind in ("sma", "ema"):
        v = values[kind][at] if at >= 0 else None
        if v is None:
            parts.append(missing(g["indicators"][kind]["needed"][str(period)]))
        else:
            close = closed_bars[at]["c"]  # integer cents, exact
            rel = "above" if close > v else "below" if close < v else "equal"
            keep = {"above": lambda r: close / 100 > r, "below": lambda r: close / 100 < r, "equal": lambda r: True}[rel]
            parts.append(text[rel].format(close=f"{close / 100:.2f}", value=shown(v / 100, 2, keep), n=period, unit=unit))
    elif kind == "rsi":
        v = values["rsi"][at] if at >= 0 else None
        if v is None:
            parts.append(missing(g["indicators"]["rsi"]["needed"][str(period)]))
        else:
            zone = _rsi_zone(v)
            parts.append(text[zone].format(value=shown(v, 1, lambda r: _rsi_zone(r) == zone)))
    else:
        line = values["macd"][at] if at >= 0 else None
        if line is None:
            parts.append(missing(g["indicators"]["macd"]["needed"]["line"]))
        else:
            m, sig = line / 100, values["signal"][at]
            sig = None if sig is None else sig / 100
            side, rel = _side(m), None if sig is None else _compare(m, sig)
            for d in range(2, 7):  # one precision for both numbers, so the shown pair tells the same story
                mt, st = shown(m, d, lambda r: True), None if sig is None else shown(sig, d, lambda r: True)
                if _side(float(mt)) == side and (sig is None or _compare(float(mt), float(st)) == rel):
                    break
            parts.append(text["line_" + side].format(macd=mt, unit=unit))
            parts.append(text["signal_missing"].format(units=units) if sig is None
                         else text["signal_" + rel].format(signal=st))
            h = values["histogram"][at]
            prev = values["histogram"][at - 1] if at >= 1 else None
            if h is not None and prev is not None and h != 0 and prev != 0:  # a zero gap has no side to compare
                change = ("crossed" if (h > 0) != (prev > 0) else "widened" if abs(h) > abs(prev)
                          else "narrowed" if abs(h) < abs(prev) else "unchanged")
                parts.append(text[change].format(unit=unit))
    if timeframe == "weekly" and last_status == "partial":
        parts.append(shared["partial_week"])
    elif timeframe == "weekly" and last_status == "final_short":
        parts.append(shared["final_short_week"].format(days=last_days))
    return " ".join(parts)
