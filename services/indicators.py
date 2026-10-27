"""Analysis Toolbox maths (P4): SMA, EMA, RSI and MACD over closing prices, and weekly bars from daily ones.

Every function is causal: the value at index i uses only inputs 0..i, so callers that pass bars up to the current
simulated day can never see a later price. Too little history gives None ("Not enough data"); nothing is estimated.
Results are educational display values only and never feed paper_engine, balances or fills."""
from datetime import date

# The only periods the toolbox offers (owner decision: presets only).
PRESETS = {"sma": (20, 50), "ema": (12, 26), "rsi": (14,), "macd": ((12, 26, 9),)}


def sma(values, n):
    out = []
    for i in range(len(values)):
        out.append(None if i < n - 1 else sum(values[i - n + 1:i + 1]) / n)
    return out


def ema(values, n):
    """Seeded with the SMA of the first n available values, then k = 2 / (n + 1). Leading None values are skipped,
    so it can smooth a series that itself starts late (the MACD line)."""
    out, k, prev, seen = [], 2 / (n + 1), None, []
    for v in values:
        if v is None:
            out.append(None)
            continue
        if prev is None:
            seen.append(v)
            if len(seen) < n:
                out.append(None)
                continue
            prev = sum(seen) / n
        else:
            prev = v * k + prev * (1 - k)
        out.append(prev)
    return out


def rsi(values, n=14):
    """Wilder's RSI. Needs n + 1 closes. No gains and no losses gives 50; only gains 100; only losses 0."""
    out = [None] * len(values)
    if len(values) <= n:
        return out
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gain = sum(max(c, 0) for c in changes[:n]) / n
    loss = sum(max(-c, 0) for c in changes[:n]) / n
    for i in range(n, len(values)):
        if i > n:
            c = changes[i - 1]
            gain = (gain * (n - 1) + max(c, 0)) / n
            loss = (loss * (n - 1) + max(-c, 0)) / n
        out[i] = 50.0 if gain == loss == 0 else 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    return out


def macd(values, fast=12, slow=26, signal=9):
    """MACD line = EMA(fast) - EMA(slow); signal = EMA(signal) of the MACD line; histogram = MACD - signal.
    The line needs `slow` closes and the signal `slow + signal - 1`."""
    line = [None if a is None or b is None else a - b for a, b in zip(ema(values, fast), ema(values, slow))]
    sig = ema(line, signal)
    hist = [None if a is None or b is None else a - b for a, b in zip(line, sig)]
    return {"macd": line, "signal": sig, "histogram": hist}


def weekly(dates, bars, final_day):
    """Monday-to-Friday weekly bars from daily ones (ISO dates and {o, h, l, c, v} bars up to today), dated by each
    week's first trading day. A week is complete once a later trading day exists or its last day is a Friday. The
    last week is otherwise "partial", or "final_short" when today is the scenario's final simulated day."""
    weeks = []
    for d, b in zip(dates, bars):
        key = date.fromisoformat(d).isocalendar()[:2]
        if weeks and weeks[-1]["key"] == key:
            w = weeks[-1]
            w.update(h=max(w["h"], b["h"]), l=min(w["l"], b["l"]), c=b["c"], v=w["v"] + b["v"], end=d,
                     days=w["days"] + 1)
        else:
            weeks.append({"key": key, "time": d, "end": d, "days": 1, "o": b["o"], "h": b["h"], "l": b["l"],
                          "c": b["c"], "v": b["v"]})
    for i, w in enumerate(weeks):
        w["status"] = "complete"
        if i == len(weeks) - 1 and date.fromisoformat(w["end"]).weekday() != 4:
            w["status"] = "final_short" if final_day else "partial"
        del w["key"]
    return weeks


def completed(weeks):
    """The weeks that weekly indicators may use: never the Partial Week."""
    return [w for w in weeks if w["status"] != "partial"]


def _dollars(values, places=4):
    return [None if v is None else round(v / 100, places) + 0.0 for v in values]  # + 0.0 turns -0.0 into 0.0


def compute(kind, period, closes_cents):
    """One preset indicator over integer-cent closes, in display units: dollars (4 decimals) for SMA, EMA and MACD,
    0-100 (2 decimals) for RSI. Returns {series name: values aligned with closes_cents}."""
    if kind not in PRESETS or period not in PRESETS[kind]:
        raise ValueError(f"Not an offered indicator preset: {kind} {period}")
    if kind == "sma":
        return {"sma": _dollars(sma(closes_cents, period))}
    if kind == "ema":
        return {"ema": _dollars(ema(closes_cents, period))}
    if kind == "rsi":
        return {"rsi": [None if v is None else round(v, 2) for v in rsi(closes_cents, period)]}
    return {name: _dollars(values) for name, values in macd(closes_cents, *period).items()}
