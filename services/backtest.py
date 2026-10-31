"""Test a strategy (P5): replays one preset rule and buy-and-hold on one ticker's daily bars, in integer cents and whole
shares, and measures both over the same days. Pure and deterministic; it never imports or calls the Practice Trading
engine, and nothing here reaches a practice session, balance, order or fill. Rules, day numbering and metrics:
docs/P5_BRIEF.md sections 3 and 4.

Days are zero-based indices (the interface shows index + 1). Indices 0..START are warm-up price history for the
indicators only; every run starts with START_CASH_CENTS in cash and no shares at the close of its start day, decides
after each close from data up to that close, and fills at the next day's open. Callers pass bars up to the last day
they may see (the current practice day), and the signals are computed from those bars alone, so no later price can
influence a decision.

Decisions are exact: SMA and RSI comparisons are made in integers (see `signals`), so a floating-point rounding error
can never create or hide a signal. The chart lines still come from services.indicators (same definitions, floats)."""
import math
from fractions import Fraction

START_CASH_CENTS = 1_000_000  # $10,000.00 of fictional cash
START = 49  # Day 50: the first close with an SMA 50 value; everyone holds cash at its close
MIN_EVALUATION_DAYS = 20
NEEDED_DAYS = START + MIN_EVALUATION_DAYS + 1  # 70 trading days of history
MIN_HALF_DAYS = 40  # each half needs 40 evaluation days, so halves start at L - START >= 80
SLIPPAGE_BPS = {"example": 10, "none": 0}  # 0.10% of the open, against the trader; commission is $0
RULES = ("sma_cross", "rsi_threshold")
FAST, SLOW = 20, 50
RSI_PERIOD, RSI_LOW, RSI_HIGH = 14, 30, 70
SKIP_REASON = "The cash did not cover one share at this price."


def fill_price(side, open_cents, costs):
    """The fill price in cents: rounded up for a buy and down for a sell, so costs are never understated. A price below
    one cent (a 1-cent open sold with example costs) is refused rather than filled at zero."""
    bps = SLIPPAGE_BPS[costs]
    if side == "buy":
        price = -(-open_cents * (10_000 + bps) // 10_000)
    else:
        price = open_cents * (10_000 - bps) // 10_000
    if price < 1:
        raise ValueError(f"A {side} at an open of {open_cents} cents has no positive fill price.")
    return price


def signals(closes):
    """Exact per-day signal inputs from integer closes, each using closes up to that day only.

    above[i]: SMA 20 > SMA 50, i.e. sum20 / 20 > sum50 / 50, i.e. 5 * sum20 > 2 * sum50 (None before index 49).

    zone[i]: "low" (RSI < 30), "high" (RSI > 70) or "mid", from index 14, with services.indicators.rsi's Wilder
    definition: g_14 = (sum of the first 14 gains) / 14, then g_i = (13 * g_(i-1) + gain_i) / 14, and the same for
    losses. Writing g_i = A_i / 14^(i-13) gives A_14 = the first 14 gains' sum and A_i = 13 * A_(i-1) + gain_i *
    14^(i-14), all integers; losses B_i share the same denominator, so g / l = A / B exactly. RSI = 100 - 100 / (1 + A /
    B) is below 30 iff A / B < 3 / 7 (7A < 3B), above 70 iff A / B > 7 / 3 (3A > 7B). B = 0 falls out: A = 0 gives
    "mid" (the RSI 50 convention), A > 0 gives "high" (RSI 100). Exactly 30 or 70 is "mid"."""
    above, zone = [None] * len(closes), [None] * len(closes)
    prefix = [0]
    for c in closes:
        prefix.append(prefix[-1] + c)
    for i in range(SLOW - 1, len(closes)):
        above[i] = 5 * (prefix[i + 1] - prefix[i + 1 - FAST]) > 2 * (prefix[i + 1] - prefix[i + 1 - SLOW])
    n = RSI_PERIOD
    if len(closes) > n:
        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        a, b, scale = sum(max(c, 0) for c in changes[:n]), sum(max(-c, 0) for c in changes[:n]), 1
        for i in range(n, len(closes)):
            if i > n:
                scale *= n  # 14^(i-14)
                a = (n - 1) * a + max(changes[i - 1], 0) * scale
                b = (n - 1) * b + max(-changes[i - 1], 0) * scale
            zone[i] = "low" if 7 * a < 3 * b else "high" if 3 * a > 7 * b else "mid"
    return {"above": above, "zone": zone}


def decide(rule, t, start, holding, series):
    """The decision at the close of day t: "buy", "sell" or None. Uses series values at t (and t - 1 for a crossing)
    only. A crossing needs the comparison on both days; equal averages count as not above. RSI thresholds are strict."""
    if rule == "buy_hold":
        return "buy" if t == start and not holding else None
    if rule == "sma_cross":
        above = series["above"]
        if t < 1 or above[t - 1] is None or above[t] is None:
            return None
        if not holding and above[t] and not above[t - 1]:
            return "buy"
        if holding and above[t - 1] and not above[t]:
            return "sell"
        return None
    zone = series["zone"][t]
    if not holding and zone == "low":
        return "buy"
    if holding and zone == "high":
        return "sell"
    return None


def simulate(dates, bars, rule, costs, start=START):
    """One run from the close of `start` to the last bar given, starting from START_CASH_CENTS and no shares whatever
    `start` is. Returns daily values, fills, skipped entries, a signal on the last day that could not be acted on, and
    the total cost of slippage."""
    if rule not in RULES + ("buy_hold",) or costs not in SLIPPAGE_BPS:
        raise ValueError("Unknown rule or cost setting.")
    last = len(bars) - 1
    if len(dates) != len(bars) or not 0 <= start < last:
        raise ValueError("The run needs at least one day after its start.")
    for i, b in enumerate(bars):
        for key in ("o", "c"):
            if type(b.get(key)) is not int or b[key] < 1:
                raise ValueError(f"Bar {i} has no positive whole-cent {key!r} price.")
    closes = [b["c"] for b in bars]
    series = signals(closes)
    cash, shares, pending = START_CASH_CENTS, 0, None
    values, fills, skipped, unacted, costs_paid = [], [], [], None, 0
    for t in range(start, last + 1):
        if pending:
            side, signal = pending
            pending = None
            open_cents = bars[t]["o"]
            price = fill_price(side, open_cents, costs)
            count = cash // price if side == "buy" else shares
            if count == 0:  # only a buy can reach this: the cash does not cover one share
                skipped.append({"signal_index": signal, "index": t, "date": dates[t], "side": side,
                                "open_cents": open_cents, "price_cents": price, "code": "cash_below_one_share",
                                "reason": SKIP_REASON})
            else:
                amount = count * price
                cash, shares = (cash - amount, count) if side == "buy" else (cash + amount, 0)
                cost = abs(price - open_cents) * count
                costs_paid += cost
                if cash < 0 or shares < 0:
                    raise RuntimeError("Backtest accounting went negative.")  # unreachable: no borrowing, no shorting
                fills.append({"signal_index": signal, "signal_date": dates[signal], "index": t, "date": dates[t],
                              "side": side, "shares": count, "open_cents": open_cents, "price_cents": price,
                              "amount_cents": amount, "cost_cents": cost, "cash_after_cents": cash})
        values.append({"index": t, "date": dates[t], "cash_cents": cash, "shares": shares, "close_cents": closes[t],
                       "value_cents": cash + shares * closes[t]})
        decision = decide(rule, t, start, shares > 0, series)
        if decision and t == last:
            unacted = {"index": t, "date": dates[t], "side": decision}
        elif decision:
            pending = (decision, t)
    return {"rule": rule, "costs": costs, "start_index": start, "last_index": last, "values": values, "fills": fills,
            "skipped": skipped, "unacted_signal": unacted, "costs_paid_cents": costs_paid}


def pct(ratio):
    """An exact ratio as a percentage rounded half away from zero to two decimals (0.12345 -> 12.35)."""
    hundredths = math.floor(abs(Fraction(ratio)) * 10_000 + Fraction(1, 2))
    return math.copysign(hundredths, ratio) / 100 if hundredths else 0.0


def sqrt_pct(variance):
    """sqrt(variance) as a percentage rounded half up to two decimals, exactly: the result is m / 100 for the largest m
    with (m - 1/2) / 10_000 <= sqrt(variance), i.e. (2m - 1)^2 <= 4 * 10^8 * variance."""
    y = 4 * 10 ** 8 * Fraction(variance)
    s = math.isqrt(y.numerator // y.denominator)  # largest s with s^2 <= y, since s^2 is a whole number
    return ((s + 1) // 2) / 100


def metrics(sim):
    """Brief section 4 from a simulate() result: integer-cent values from the start close to the last close, so
    L - start daily changes. Percentages are display values; the exact inputs (cents, indices) are returned beside
    them."""
    values = sim["values"]
    v = [d["value_cents"] for d in values]
    days = len(v) - 1
    peak_at, worst, worst_at = 0, Fraction(0), None  # the running peak is the first day its value was reached
    for t in range(1, len(v)):
        if v[t] > v[peak_at]:
            peak_at = t
        elif Fraction(v[peak_at] - v[t], v[peak_at]) > worst:  # strict: a tie keeps the earlier trough
            worst, worst_at = Fraction(v[peak_at] - v[t], v[peak_at]), (peak_at, t)
    changes = [Fraction(v[t], v[t - 1]) - 1 for t in range(1, len(v))]
    mean = sum(changes) / days
    variance = sum((c - mean) ** 2 for c in changes) / (days - 1) if days > 1 else None
    invested = sum(1 for d in values[1:] if d["shares"] > 0)
    point = lambda t: {"index": values[t]["index"], "date": values[t]["date"], "value_cents": v[t]}
    return {"start_value_cents": v[0], "final_value_cents": v[-1],
            "total_return_pct": pct(Fraction(v[-1] - START_CASH_CENTS, START_CASH_CENTS)),
            "max_drawdown_pct": pct(worst),
            "max_drawdown": {"peak": point(worst_at[0]), "trough": point(worst_at[1])} if worst_at else None,
            "daily_volatility_pct": None if variance is None else sqrt_pct(variance),
            "buys": sum(1 for f in sim["fills"] if f["side"] == "buy"),
            "sells": sum(1 for f in sim["fills"] if f["side"] == "sell"),
            "evaluation_days": days, "days_invested": invested, "days_invested_pct": pct(Fraction(invested, days)),
            "costs_paid_cents": sim["costs_paid_cents"]}


def compare(dates, bars, rule, costs, start=START):
    """The rule and buy-and-hold on the same bars from the same start, each with its metrics, and the difference in
    total return in percentage points (from the exact final values, then rounded)."""
    strategy, benchmark = (simulate(dates, bars, r, costs, start) for r in (rule, "buy_hold"))
    for side in (strategy, benchmark):
        side["metrics"] = metrics(side)
    gap = strategy["values"][-1]["value_cents"] - benchmark["values"][-1]["value_cents"]
    return {"strategy": strategy, "benchmark": benchmark, "difference_pp": pct(Fraction(gap, START_CASH_CENTS))}


def halves(dates, bars, rule, costs):
    """Two independent runs, each from $10,000 and no shares (brief 3.8): the earlier half START..M on bars up to M,
    the later half M..L with the closes before M used for its signals only. None when either half would have fewer
    than MIN_HALF_DAYS evaluation days. Descriptive only: nothing is fitted on either half."""
    last = len(bars) - 1
    if last - START < 2 * MIN_HALF_DAYS:
        return None
    mid = START + (last - START) // 2
    return {"midpoint_index": mid, "earlier": compare(dates[:mid + 1], bars[:mid + 1], rule, costs, START),
            "later": compare(dates, bars, rule, costs, mid)}


def run(dates, bars, rule, costs):
    """The rule against buy-and-hold over START..L, with metrics and halves. Too little history gives result None."""
    if rule not in RULES:
        raise ValueError("Unknown rule.")
    if len(bars) < NEEDED_DAYS:
        return {"result": None, "needed_days": NEEDED_DAYS, "available_days": len(bars)}
    result = compare(dates, bars, rule, costs)
    result["halves"] = halves(dates, bars, rule, costs)
    return {"result": result, "needed_days": NEEDED_DAYS, "available_days": len(bars)}
