"""Test a strategy (P5): replays one preset rule and buy-and-hold on one ticker's daily bars, in integer cents and whole
shares. Pure and deterministic; it never imports or calls the Practice Trading engine, and nothing here reaches a
practice session, balance, order or fill. Rules and day numbering: docs/P5_BRIEF.md section 3.

Days are zero-based indices (the interface shows index + 1). Indices 0..START are warm-up price history for the
indicators only; every run starts with START_CASH_CENTS in cash and no shares at the close of its start day, decides
after each close from data up to that close, and fills at the next day's open. Callers pass bars up to the last day
they may see (the current practice day), and indicators are computed from those bars alone, so no later price can
influence a decision."""
from services import indicators

START_CASH_CENTS = 1_000_000  # $10,000.00 of fictional cash
START = 49  # Day 50: the first close with an SMA 50 value; everyone holds cash at its close
MIN_EVALUATION_DAYS = 20
NEEDED_DAYS = START + MIN_EVALUATION_DAYS + 1  # 70 trading days of history
SLIPPAGE_BPS = {"example": 10, "none": 0}  # 0.10% of the open, against the trader; commission is $0
RULES = ("sma_cross", "rsi_threshold")
FAST, SLOW = 20, 50
RSI_PERIOD, RSI_LOW, RSI_HIGH = 14, 30, 70


def fill_price(side, open_cents, costs):
    """The fill price in cents: rounded up for a buy and down for a sell, so costs are never understated."""
    bps = SLIPPAGE_BPS[costs]
    if side == "buy":
        return -(-open_cents * (10_000 + bps) // 10_000)
    return open_cents * (10_000 - bps) // 10_000


def decide(rule, t, start, holding, series):
    """The decision at the close of day t: "buy", "sell" or None. Uses series values at t (and t - 1 for a crossing)
    only. A crossing needs both averages on both days; equal averages count as not above. RSI thresholds are strict."""
    if rule == "buy_hold":
        return "buy" if t == start and not holding else None
    if rule == "sma_cross":
        fast, slow = series["fast"], series["slow"]
        if t < 1 or None in (fast[t - 1], slow[t - 1], fast[t], slow[t]):
            return None
        was_above, above = fast[t - 1] > slow[t - 1], fast[t] > slow[t]
        if not holding and above and not was_above:
            return "buy"
        if holding and was_above and not above:
            return "sell"
        return None
    rsi = series["rsi"][t]
    if rsi is None:
        return None
    if not holding and rsi < RSI_LOW:
        return "buy"
    if holding and rsi > RSI_HIGH:
        return "sell"
    return None


def simulate(dates, bars, rule, costs, start=START):
    """One run from the close of `start` to the last bar given. Returns daily values, fills, skipped entries, a signal
    on the last day that could not be acted on, and the total cost of slippage."""
    if rule not in RULES + ("buy_hold",) or costs not in SLIPPAGE_BPS:
        raise ValueError("Unknown rule or cost setting.")
    last = len(bars) - 1
    if len(dates) != len(bars) or not 0 <= start < last:
        raise ValueError("The run needs at least one day after its start.")
    closes = [b["c"] for b in bars]
    series = {"fast": indicators.sma(closes, FAST), "slow": indicators.sma(closes, SLOW),
              "rsi": indicators.rsi(closes, RSI_PERIOD)}
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
                                "open_cents": open_cents, "price_cents": price,
                                "reason": "The cash did not cover one share at this price."})
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


def run(dates, bars, rule, costs):
    """The rule and buy-and-hold on the same days from the same start. Too little history gives result None."""
    if rule not in RULES:
        raise ValueError("Unknown rule.")
    if len(bars) < NEEDED_DAYS:
        return {"result": None, "needed_days": NEEDED_DAYS, "available_days": len(bars)}
    result = {"strategy": simulate(dates, bars, rule, costs), "benchmark": simulate(dates, bars, "buy_hold", costs)}
    return {"result": result, "needed_days": NEEDED_DAYS, "available_days": len(bars)}
