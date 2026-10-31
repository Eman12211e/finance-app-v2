"""P5 steps 2 and 3: the backtesting engine (services/backtest.py) against docs/P5_BRIEF.md sections 3 and 4, a separate
reference written here with exact integer, fraction and 60-digit decimal arithmetic, and the accounting, start, boundary,
metric, halves and no-look-ahead rules. Offline: only the fixed synthetic scenario files are read."""
import copy
import json
import math
import os
import random
import statistics
from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction

import pytest

from services import backtest as bt
from services import indicators
from services import paper_market

ROOT = os.path.join(os.path.dirname(__file__), "..")
MARKETS = [paper_market.get(s) for s in paper_market.scenario_ids()]
CASES = [(m, s) for m in MARKETS for s in m["symbols"]]
CASE_IDS = [s for _, s in CASES]
RULES = ("sma_cross", "rsi_threshold", "buy_hold")


def bars_from(closes, opens=None):
    """Hand-made daily bars: opens default to the closes; dates are opaque labels to the engine."""
    opens = opens or closes
    bars = [{"o": o, "h": max(o, c), "l": min(o, c), "c": c, "v": 0} for o, c in zip(opens, closes)]
    return [f"d{i:03}" for i in range(len(bars))], bars


# ---- an independent reference: exact arithmetic, textbook definitions, plain loops ----

def ref_above(closes, i):
    """SMA 20 > SMA 50 at i, exactly: sum20 / 20 > sum50 / 50."""
    return 5 * sum(closes[i - 19:i + 1]) > 2 * sum(closes[i - 49:i + 1])


def ref_rsi_zones(closes, n=14):
    """'low' (RSI < 30), 'high' (RSI > 70) or 'mid' per day, from Wilder's averages kept as exact fractions."""
    zones = [None] * len(closes)
    gains = [max(closes[i] - closes[i - 1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0) for i in range(1, len(closes))]
    for i in range(n, len(closes)):
        if i == n:
            g, l = Fraction(sum(gains[:n]), n), Fraction(sum(losses[:n]), n)
        else:
            g, l = (g * (n - 1) + gains[i - 1]) / n, (l * (n - 1) + losses[i - 1]) / n
        if l == 0:
            zones[i] = "mid" if g == 0 else "high"  # RSI 50 or 100
        else:  # RSI = 100 - 100 / (1 + g / l): below 30 when g / l < 3 / 7, above 70 when g / l > 7 / 3
            zones[i] = "low" if g / l < Fraction(3, 7) else "high" if g / l > Fraction(7, 3) else "mid"
    return zones


def ref_price(side, open_cents, costs):
    exact = Fraction(open_cents * (10_000 + (10 if costs == "example" else 0) * (1 if side == "buy" else -1)), 10_000)
    return math.ceil(exact) if side == "buy" else math.floor(exact)


def ref_run(dates, bars, rule, costs, start=49):
    closes = [b["c"] for b in bars]
    zones = ref_rsi_zones(closes)
    cash, held, order = 1_000_000, 0, None
    values, fills, skipped, unacted, paid = [], [], [], None, 0
    for day in range(start, len(bars)):
        if order:
            side, signal_day = order
            order = None
            o = bars[day]["o"]
            p = ref_price(side, o, costs)
            if side == "buy":
                n = 0
                while (n + 1) * p <= cash:  # deliberately slow: count whole shares one at a time
                    n += 1
                if n == 0:
                    skipped.append({"signal_index": signal_day, "index": day, "date": dates[day], "side": side,
                                    "open_cents": o, "price_cents": p, "code": "cash_below_one_share",
                                    "reason": "The cash did not cover one share at this price."})
                else:
                    cash -= n * p
                    held = n
            else:
                n = held
                cash += n * p
                held = 0
            if n:
                paid += abs(p - o) * n
                fills.append({"signal_index": signal_day, "signal_date": dates[signal_day], "index": day,
                              "date": dates[day], "side": side, "shares": n, "open_cents": o, "price_cents": p,
                              "amount_cents": n * p, "cost_cents": abs(p - o) * n, "cash_after_cents": cash})
        values.append({"index": day, "date": dates[day], "cash_cents": cash, "shares": held,
                       "close_cents": closes[day], "value_cents": cash + held * closes[day]})
        want = None
        if rule == "buy_hold":
            want = "buy" if day == start and not held else None
        elif rule == "sma_cross":
            if day >= 50:
                if not held and ref_above(closes, day) and not ref_above(closes, day - 1):
                    want = "buy"
                elif held and ref_above(closes, day - 1) and not ref_above(closes, day):
                    want = "sell"
        else:
            want = "buy" if not held and zones[day] == "low" else "sell" if held and zones[day] == "high" else None
        if want and day == len(bars) - 1:
            unacted = {"index": day, "date": dates[day], "side": want}
        elif want:
            order = (want, day)
    return {"rule": rule, "costs": costs, "start_index": start, "last_index": len(bars) - 1, "values": values,
            "fills": fills, "skipped": skipped, "unacted_signal": unacted, "costs_paid_cents": paid}


def check_accounting(r, bars):
    """Replays the fills against the daily records: exact cash and shares, no borrowing, no shorting, costs inside the
    fill prices, all in and all out."""
    cash, shares, bought, sold = bt.START_CASH_CENTS, 0, 0, 0
    fills = {f["index"]: f for f in r["fills"]}
    assert len(fills) == len(r["fills"])  # at most one fill per day
    for v in r["values"]:
        f = fills.get(v["index"])
        if f:
            assert f["index"] == f["signal_index"] + 1 and f["signal_index"] >= r["start_index"]
            assert f["open_cents"] == bars[f["index"]]["o"]
            assert f["price_cents"] == bt.fill_price(f["side"], f["open_cents"], r["costs"])
            assert f["amount_cents"] == f["shares"] * f["price_cents"] and f["shares"] > 0
            assert f["cost_cents"] == abs(f["price_cents"] - f["open_cents"]) * f["shares"]
            if r["costs"] == "none":
                assert f["price_cents"] == f["open_cents"] and f["cost_cents"] == 0
            if f["side"] == "buy":
                assert shares == 0 and f["amount_cents"] <= cash  # never borrows
                assert cash - f["amount_cents"] < f["price_cents"]  # all in: less than one more share is left
                cash -= f["amount_cents"]
                shares = f["shares"]
                bought += f["amount_cents"]
            else:
                assert f["shares"] == shares > 0  # sells exactly what it holds: never short
                cash += f["amount_cents"]
                shares = 0
                sold += f["amount_cents"]
            assert f["cash_after_cents"] == cash
        assert cash >= 0 and shares >= 0
        assert (v["cash_cents"], v["shares"]) == (cash, shares)
        assert v["close_cents"] == bars[v["index"]]["c"]
        assert v["value_cents"] == cash + shares * v["close_cents"]
    assert cash == bt.START_CASH_CENTS - bought + sold
    assert r["costs_paid_cents"] == sum(f["cost_cents"] for f in r["fills"])
    for s in r["skipped"]:
        assert s["side"] == "buy" and s["price_cents"] > r["values"][s["index"] - r["start_index"] - 1]["cash_cents"]


def dec_pct(x):
    """A Decimal ratio as a percentage, rounded half away from zero to two decimals."""
    return float((x * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) or 0.0


def ref_metrics(sim):
    """Brief section 4 by other means: brute-force drawdown over every pair of days, 60-digit decimal volatility."""
    vals = sim["values"]
    v = [d["value_cents"] for d in vals]
    falls = [max(Fraction(v[i] - v[j], v[i]) for i in range(j)) for j in range(1, len(v))]  # every pair of days
    worst, at = max(falls + [Fraction(0)]), None
    if worst > 0:  # the earliest trough with the largest fall, and the first day its peak value was reached
        j = falls.index(worst) + 1
        at = (v.index(max(v[:j])), j)
    with localcontext() as ctx:
        ctx.prec = 60
        r = [Decimal(v[t]) / Decimal(v[t - 1]) - 1 for t in range(1, len(v))]
        mean = sum(r) / len(r)
        vol = dec_pct(((sum((x - mean) ** 2 for x in r)) / (len(r) - 1)).sqrt())
        total = dec_pct(Decimal(v[-1] - 1_000_000) / Decimal(1_000_000))
        dd = dec_pct(Decimal(worst.numerator) / Decimal(worst.denominator))
    point = lambda t: {"index": vals[t]["index"], "date": vals[t]["date"], "value_cents": v[t]}
    held = len([d for d in vals[1:] if d["shares"]])
    with localcontext() as ctx:
        ctx.prec = 60
        invested = dec_pct(Decimal(held) / Decimal(len(v) - 1))
    return {"start_value_cents": v[0], "final_value_cents": v[-1], "total_return_pct": total,
            "max_drawdown_pct": dd, "max_drawdown": {"peak": point(at[0]), "trough": point(at[1])} if at else None,
            "daily_volatility_pct": vol, "buys": len([f for f in sim["fills"] if f["side"] == "buy"]),
            "sells": len([f for f in sim["fills"] if f["side"] == "sell"]), "evaluation_days": len(v) - 1,
            "days_invested": held, "days_invested_pct": invested, "costs_paid_cents": sim["costs_paid_cents"]}


def run_all(dates, bars, rule, costs):
    return bt.simulate(dates, bars, rule, costs)


# ---- prices and costs ----

@pytest.mark.parametrize("open_cents, costs, buy, sell", [
    (10_000, "example", 10_010, 9_990), (4_965, "example", 4_970, 4_960),  # 4969.965 up, 4960.035 down
    (10_001, "example", 10_012, 9_990),  # 10011.001 up, 9990.999 down
    (4_965, "none", 4_965, 4_965), (1, "none", 1, 1)])
def test_fill_prices_round_against_the_trader(open_cents, costs, buy, sell):
    assert bt.fill_price("buy", open_cents, costs) == buy == ref_price("buy", open_cents, costs)
    assert bt.fill_price("sell", open_cents, costs) == sell == ref_price("sell", open_cents, costs)


# ---- the whole engine against the reference, every symbol, rule and cost setting ----

@pytest.mark.parametrize("market, symbol", CASES, ids=CASE_IDS)
@pytest.mark.parametrize("costs", ["example", "none"])
def test_engine_equals_the_exact_reference_for_every_symbol(market, symbol, costs):
    dates, bars = market["dates"], market["bars"][symbol]
    for last in sorted({bt.NEEDED_DAYS - 1, 100, len(bars) // 2 + 40, len(bars) - 1} & set(range(len(bars)))):
        for rule in RULES:
            got = bt.simulate(dates[:last + 1], bars[:last + 1], rule, costs)
            assert got == ref_run(dates[:last + 1], bars[:last + 1], rule, costs), (symbol, rule, last)


@pytest.mark.parametrize("market, symbol", CASES, ids=CASE_IDS)
def test_accounting_is_exact_on_every_day_for_every_symbol(market, symbol):
    dates, bars = market["dates"], market["bars"][symbol]
    for last in range(bt.NEEDED_DAYS - 1, len(bars), 7):
        for rule in RULES:
            for costs in bt.SLIPPAGE_BPS:
                check_accounting(bt.simulate(dates[:last + 1], bars[:last + 1], rule, costs), bars)


def test_the_real_scenarios_exercise_both_rules_and_both_sides():
    """Guards the tests above against passing vacuously: across the markets both rules buy and sell."""
    seen = set()
    for market, symbol in CASES:
        for rule in ("sma_cross", "rsi_threshold"):
            seen |= {(rule, f["side"]) for f in run_all(market["dates"], market["bars"][symbol], rule, "example")["fills"]}
    assert seen == {(r, s) for r in ("sma_cross", "rsi_threshold") for s in ("buy", "sell")}


# ---- the same start for every comparison ----

@pytest.mark.parametrize("market, symbol", CASES, ids=CASE_IDS)
def test_rule_and_benchmark_start_alike_on_the_same_dates(market, symbol):
    dates, bars = market["dates"], market["bars"][symbol]
    for rule in ("sma_cross", "rsi_threshold"):
        res = bt.run(dates, bars, rule, "example")["result"]
        s, b = res["strategy"], res["benchmark"]
        assert [(v["index"], v["date"]) for v in s["values"]] == [(v["index"], v["date"]) for v in b["values"]]
        assert s["values"][0]["index"] == b["values"][0]["index"] == 49  # the Day 50 close
        for r in (s, b):
            assert r["values"][0] == {"index": 49, "date": dates[49], "cash_cents": 1_000_000, "shares": 0,
                                      "close_cents": bars[49]["c"], "value_cents": 1_000_000}
            assert all(f["index"] >= 50 for f in r["fills"])  # the Day 51 open at the earliest
        assert (b["fills"][0]["signal_index"], b["fills"][0]["index"], b["fills"][0]["side"]) == (49, 50, "buy")
        assert len(b["fills"]) == 1
        if rule == "sma_cross":
            assert all(f["index"] >= 51 for f in s["fills"])  # the first crossing is detectable on Day 51


def test_no_trade_is_presumed_when_the_averages_already_crossed_before_the_start():
    """Where SMA 20 is already above SMA 50 on Day 50, the rule still starts in cash and waits for a fresh cross up."""
    found = 0
    for market, symbol in CASES:
        dates, bars = market["dates"], market["bars"][symbol]
        closes = [b["c"] for b in bars]
        if not ref_above(closes, 49):
            continue
        found += 1
        r = run_all(dates, bars, "sma_cross", "example")
        assert r["values"][1]["shares"] == 0  # nothing bought at the Day 51 open
        if r["fills"]:
            first = r["fills"][0]
            assert first["side"] == "buy"
            assert ref_above(closes, first["signal_index"]) and not ref_above(closes, first["signal_index"] - 1)
    assert found  # the scenarios include this case


def test_a_steady_rise_never_crosses_so_the_crossover_rule_never_trades():
    dates, bars = bars_from([10_000 + 25 * i for i in range(120)])
    r = run_all(dates, bars, "sma_cross", "example")
    assert r["fills"] == [] and r["unacted_signal"] is None
    assert all(v["value_cents"] == 1_000_000 for v in r["values"])


def test_rsi_below_30_on_the_start_day_fills_at_the_day_51_open_like_buy_and_hold():
    dates, bars = bars_from([20_000 - 30 * i for i in range(80)])  # falling every day: RSI 0
    r, b = run_all(dates, bars, "rsi_threshold", "none"), run_all(dates, bars, "buy_hold", "none")
    assert (r["fills"][0]["signal_index"], r["fills"][0]["index"]) == (49, 50) == \
        (b["fills"][0]["signal_index"], b["fills"][0]["index"])
    assert r["fills"][0]["price_cents"] == bars[50]["o"]


# ---- decision boundaries ----

@pytest.mark.parametrize("above, holding, expected", [
    ([False, False], False, None),    # not above on both days (equal counts as not above): no cross
    ([False, True], False, "buy"),    # a cross up
    ([False, True], True, None),      # a cross up while holding does nothing
    ([True, False], True, "sell"),    # a cross down
    ([True, False], False, None),     # a cross down while in cash does nothing
    ([True, True], False, None),      # above on both days: no cross, so no presumed entry
    ([None, True], False, None)])     # no comparison yesterday: no crossing can be seen
def test_crossing_boundaries(above, holding, expected):
    assert bt.decide("sma_cross", 1, 0, holding, {"above": above, "zone": [None, None]}) == expected


@pytest.mark.parametrize("zone, holding, expected", [
    ("low", False, "buy"), ("low", True, None), ("high", True, "sell"), ("high", False, None),
    ("mid", False, None), ("mid", True, None), (None, False, None), (None, True, None)])
def test_rsi_zone_decisions(zone, holding, expected):
    assert bt.decide("rsi_threshold", 0, 0, holding, {"above": [None], "zone": [zone]}) == expected


def test_buy_and_hold_decides_once_on_its_start_day():
    series = {"above": [None] * 3, "zone": [None] * 3}
    assert [bt.decide("buy_hold", t, 1, False, series) for t in (1, 2)] == ["buy", None]
    assert bt.decide("buy_hold", 1, 1, True, series) is None


def test_exactly_equal_real_averages_never_count_as_a_cross():
    """Constant prices make SMA 20 equal SMA 50 every day and RSI exactly 50: neither rule ever trades."""
    dates, bars = bars_from([12_345] * 100)
    for rule in ("sma_cross", "rsi_threshold"):
        r = run_all(dates, bars, rule, "example")
        assert r["fills"] == r["skipped"] == [] and r["unacted_signal"] is None
        assert {v["value_cents"] for v in r["values"]} == {1_000_000}


# ---- fills: timing, gaps, cash and whole shares ----

def test_a_decision_at_the_close_fills_at_the_next_open_across_a_gap():
    closes = [10_000] * 60
    opens = closes[:50] + [12_000] + closes[51:]  # the Day 51 open gaps 20% above the Day 50 close
    dates, bars = bars_from(closes, opens)
    f = run_all(dates, bars, "buy_hold", "example")["fills"][0]
    assert (f["signal_index"], f["index"]) == (49, 50)
    assert (f["open_cents"], f["price_cents"]) == (12_000, 12_012)  # the open plus 0.10%, not the 10,000 close
    assert (f["shares"], f["amount_cents"], f["cash_after_cents"]) == (83, 996_996, 3_004)


def test_the_scripted_earnings_gap_is_filled_at_the_gapped_open():
    market = paper_market.get("synthetic-b")
    gap = next(e for e in market["events"] if e["kind"] == "earnings_gap")
    bars = market["bars"][gap["symbol"]]
    dates = market["dates"]
    # a buy-and-hold run that starts the day before the gap: decided at that close, filled at the gapped open
    r = bt.simulate(dates, bars, "buy_hold", "none", start=gap["day"] - 1)
    f = r["fills"][0]
    assert f["index"] == gap["day"] and f["price_cents"] == bars[gap["day"]]["o"] > bars[gap["day"] - 1]["c"]


def test_whole_shares_leave_the_remainder_in_cash():
    dates, bars = bars_from([3_001] * 70)
    f = run_all(dates, bars, "buy_hold", "none")["fills"][0]
    assert (f["shares"], f["amount_cents"], f["cash_after_cents"]) == (333, 999_333, 667)


def test_a_price_above_the_cash_skips_the_entry_and_keeps_the_cash():
    dates, bars = bars_from([2_000_000] * 70)  # $20,000 a share
    r = run_all(dates, bars, "buy_hold", "example")
    assert r["fills"] == []
    assert r["skipped"] == [{"signal_index": 49, "index": 50, "date": "d050", "side": "buy", "open_cents": 2_000_000,
                             "price_cents": 2_002_000, "code": "cash_below_one_share",
                             "reason": "The cash did not cover one share at this price."}]
    assert all((v["cash_cents"], v["shares"], v["value_cents"]) == (1_000_000, 0, 1_000_000) for v in r["values"])


def test_cash_exactly_covering_the_shares_leaves_zero_and_never_goes_negative():
    dates, bars = bars_from([10_000] * 70)  # no costs: exactly 100 shares for $10,000
    r = run_all(dates, bars, "buy_hold", "none")
    assert (r["fills"][0]["shares"], r["fills"][0]["cash_after_cents"]) == (100, 0)
    check_accounting(r, bars)


# ---- missing history, last day, end of window ----

def test_too_little_history_gives_no_result_and_says_what_is_needed():
    market = paper_market.get("synthetic-b")
    dates, bars = market["dates"], market["bars"]["SYN-HLT1"]
    assert bt.run(dates[:69], bars[:69], "sma_cross", "example") == {"result": None, "needed_days": 70,
                                                                     "available_days": 69}
    res = bt.run(dates[:70], bars[:70], "sma_cross", "example")["result"]
    assert [v["index"] for v in res["strategy"]["values"]] == list(range(49, 70))  # 20 daily changes


def test_a_signal_on_the_last_day_is_reported_not_filled():
    market = paper_market.get("synthetic-b")
    dates, bars = market["dates"], market["bars"]["SYN-CON1"]
    cut = bt.simulate(dates[:165], bars[:165], "sma_cross", "example")
    assert cut["unacted_signal"] == {"index": 164, "date": dates[164], "side": "sell"}
    assert cut["values"][-1]["shares"] > 0  # still holding at the end, valued at the last close
    later = bt.simulate(dates, bars, "sma_cross", "example")
    assert any((f["signal_index"], f["index"], f["side"]) == (164, 165, "sell") for f in later["fills"])


def test_no_trades_on_a_real_symbol_keeps_ten_thousand_dollars():
    market = paper_market.get("synthetic-b")
    r = bt.simulate(market["dates"][:161], market["bars"]["SYN-TEC1"][:161], "sma_cross", "example")
    assert r["fills"] == [] and {v["value_cents"] for v in r["values"]} == {1_000_000}


# ---- no look-ahead ----

@pytest.mark.parametrize("market, symbol", CASES, ids=CASE_IDS)
def test_every_shorter_run_is_a_prefix_of_the_full_run(market, symbol):
    """For every last day L: values up to L are identical, fills up to L are identical, and the decision on L that a
    short run reports as unacted is exactly the fill the full run makes at the next open."""
    dates, bars = market["dates"], market["bars"][symbol]
    for rule in RULES:
        full = bt.simulate(dates, bars, rule, "example")
        for last in range(bt.NEEDED_DAYS - 1, len(bars) - 1):
            cut = bt.simulate(dates[:last + 1], bars[:last + 1], rule, "example")
            assert cut["values"] == full["values"][:last - 48]
            assert cut["fills"] == [f for f in full["fills"] if f["index"] <= last]
            nxt = [f for f in full["fills"] + full["skipped"] if f["signal_index"] == last]
            expected = {"index": last, "date": dates[last], "side": nxt[0]["side"]} if nxt else None
            assert cut["unacted_signal"] == expected


@pytest.mark.parametrize("rule", RULES)
def test_changing_every_later_price_changes_no_earlier_decision(rule):
    market = paper_market.get("synthetic-b")
    dates = market["dates"]
    rng = random.Random(20261030)
    for symbol in ("SYN-HLT1", "SYN-ENR1", "SYN-CON1", "SYN-IND2"):
        bars = market["bars"][symbol]
        base = bt.simulate(dates, bars, rule, "example")
        for t in (60, 100, 150, 200):
            changed = copy.deepcopy(bars)
            for b in changed[t + 1:]:
                b["o"], b["c"] = rng.randint(500, 50_000), rng.randint(500, 50_000)
                b["h"], b["l"] = max(b["o"], b["c"]), min(b["o"], b["c"])
            other = bt.simulate(dates, changed, rule, "example")
            assert other["values"][:t - 48] == base["values"][:t - 48]
            decisions = lambda r: [(f["signal_index"], f["side"]) for f in r["fills"] + r["skipped"] if f["signal_index"] <= t]
            assert decisions(other) == decisions(base)


# ---- determinism, inputs, independence ----

def test_runs_are_repeatable_and_leave_their_inputs_unchanged():
    market = paper_market.get("synthetic-b")
    dates, bars = market["dates"], market["bars"]["SYN-ENR1"]
    before = copy.deepcopy((dates, bars))
    first = json.dumps(bt.run(dates, bars, "rsi_threshold", "example"), sort_keys=True)
    second = json.dumps(bt.run(dates, bars, "rsi_threshold", "example"), sort_keys=True)
    assert first == second and (dates, bars) == before


@pytest.mark.parametrize("call", [
    lambda d, b: bt.run(d, b, "ema_cross", "example"), lambda d, b: bt.run(d, b, "buy_hold", "example"),
    lambda d, b: bt.run(d, b, "sma_cross", "cheap"), lambda d, b: bt.simulate(d, b, "sma_cross", "example", start=69),
    lambda d, b: bt.simulate(d[:-1], b, "sma_cross", "example")])
def test_unknown_rules_costs_and_impossible_windows_are_refused(call):
    dates, bars = bars_from([10_000] * 70)
    with pytest.raises(ValueError):
        call(dates, bars)


def test_the_engine_is_independent_of_practice_trading():
    with open(os.path.join(ROOT, "services", "backtest.py"), encoding="utf-8") as f:
        source = f.read()
    assert "paper_engine" not in source and "paper_market" not in source and "import config" not in source
    for name in ("paper_engine.py", "paper_market.py"):
        with open(os.path.join(ROOT, "services", name), encoding="utf-8") as f:
            assert "backtest" not in f.read()


# ---- step 2 corrections: exact signals, invalid prices, unaffordable entries ----

def exact_rsi(closes, i, n=14):
    """RSI at i as an exact fraction, Wilder's recursion step by step (the shared indicator's definition)."""
    ch = [closes[k] - closes[k - 1] for k in range(1, i + 1)]
    g, l = Fraction(sum(max(c, 0) for c in ch[:n]), n), Fraction(sum(max(-c, 0) for c in ch[:n]), n)
    for c in ch[n:]:
        g, l = (g * (n - 1) + max(c, 0)) / n, (l * (n - 1) + max(-c, 0)) / n
    return Fraction(50) if g == l == 0 else Fraction(100) if l == 0 else 100 - 100 / (1 + g / l)


@pytest.mark.parametrize("market, symbol", CASES, ids=CASE_IDS)
def test_exact_signals_equal_the_fraction_reference_and_the_shared_float_indicators(market, symbol):
    """The integer recurrence in bt.signals gives the same comparison as the exact Fraction recursion and, away from
    exact ties, the same as services.indicators' floats: the established conventions are kept."""
    closes = [b["c"] for b in market["bars"][symbol]]
    got = bt.signals(closes)
    fast, slow, rsi = indicators.sma(closes, 20), indicators.sma(closes, 50), indicators.rsi(closes, 14)
    zones = ref_rsi_zones(closes)
    for i in range(len(closes)):
        assert got["above"][i] == (None if i < 49 else ref_above(closes, i)) == \
            (None if slow[i] is None else fast[i] > slow[i]), (symbol, i)
        assert got["zone"][i] == zones[i] == \
            (None if rsi[i] is None else "low" if rsi[i] < 30 else "high" if rsi[i] > 70 else "mid"), (symbol, i)
    for i in range(14, len(closes), 11):  # and the RSI value itself, exactly, matches the float to rounding
        assert abs(float(exact_rsi(closes, i)) - rsi[i]) < 1e-9


def test_exact_signals_equal_the_reference_on_random_small_moves():
    rng = random.Random(31)
    for _ in range(200):
        closes = [5_000]
        for _ in range(79):
            closes.append(max(1, closes[-1] + rng.choice((-3, -2, -1, 0, 1, 2, 3))))
        got, zones = bt.signals(closes), ref_rsi_zones(closes)
        assert got["zone"] == zones
        assert got["above"][49:] == [ref_above(closes, i) for i in range(49, 80)]


def rsi_closes(gains, losses):
    """15 closes whose first 14 changes are the given gains, then the given losses: RSI at index 14 is exact."""
    closes = [100_000]
    for c in list(gains) + [-x for x in losses]:
        closes.append(closes[-1] + c)
    return closes


@pytest.mark.parametrize("gains, losses, rsi, zone, decision", [
    ([300], [54] * 12 + [52], Fraction(30), "mid", None),                 # exactly 30: nothing
    ([299], [54] * 12 + [52], 100 - Fraction(100) / (1 + Fraction(299, 700)), "low", "buy"),   # 29.94...
    ([301], [54] * 12 + [52], 100 - Fraction(100) / (1 + Fraction(301, 700)), "mid", None),    # 30.06...
    ([700], [23] * 12 + [24], Fraction(70), "mid", None),                 # exactly 70: nothing
    ([701], [23] * 12 + [24], 100 - Fraction(100) / (1 + Fraction(701, 300)), "high", None),   # 70.03...
    ([699], [23] * 12 + [24], 100 - Fraction(100) / (1 + Fraction(699, 300)), "mid", None)])
def test_rsi_exactly_at_and_one_cent_either_side_of_30_and_70(gains, losses, rsi, zone, decision):
    closes = rsi_closes(gains, losses)
    assert len(closes) == 15 and exact_rsi(closes, 14) == rsi
    assert bt.signals(closes)["zone"][14] == ref_rsi_zones(closes)[14] == zone
    dates, bars = bars_from(closes + [closes[-1]])
    r = bt.simulate(dates, bars, "rsi_threshold", "none", start=14)  # in cash: only a "low" day can act
    assert [(f["signal_index"], f["side"]) for f in r["fills"]] == ([(14, decision)] if decision else [])


def test_a_float_rounding_error_at_an_exact_rsi_30_creates_no_buy():
    """Found by search: RSI is exactly 30 on index 15, but the float indicator reads 29.999999999999986. The exact
    engine sees no signal; a float comparison would have bought."""
    closes = [100000, 99878, 100080, 99794, 99738, 99566, 99550, 99644, 99369, 99351, 99514, 99229, 99289, 99296,
              99168, 99220]
    assert exact_rsi(closes, 15) == 30 and indicators.rsi(closes)[15] < 30
    assert bt.signals(closes)["zone"][15] == ref_rsi_zones(closes)[15] == "mid"
    dates, bars = bars_from(closes + [closes[-1]])
    assert bt.simulate(dates, bars, "rsi_threshold", "none", start=15)["fills"] == []


def tie_closes(offset):
    """52 closes, falling, then a close on index 50 that makes SMA 20 equal SMA 50 exactly (offset 0), or the nearest
    whole-cent close either side (offset +-1)."""
    closes = [20_000 - 40 * i for i in range(50)]
    while (2 * sum(closes[1:50]) - 5 * sum(closes[31:50])) % 3:
        closes[1] += 1  # inside SMA 50's window only, until the tie price is a whole cent
    x = (2 * sum(closes[1:50]) - 5 * sum(closes[31:50])) // 3
    return closes + [x + offset, x + offset]


@pytest.mark.parametrize("offset, above, fills", [(0, False, []), (1, True, [(50, 51, "buy")]), (-1, False, [])])
def test_averages_exactly_equal_and_one_cent_either_side(offset, above, fills):
    closes = tie_closes(offset)
    assert 5 * sum(closes[31:51]) - 2 * sum(closes[1:51]) == 3 * offset  # 100 * (SMA 20 - SMA 50)
    assert bt.signals(closes)["above"][49:51] == [False, above]
    fast, slow = indicators.sma(closes, 20), indicators.sma(closes, 50)
    assert (fast[50] > slow[50]) is above  # the float indicator agrees: an exact tie divides to equal floats
    dates, bars = bars_from(closes)
    r = bt.simulate(dates, bars, "sma_cross", "none")
    assert [(f["signal_index"], f["index"], f["side"]) for f in r["fills"]] == fills


@pytest.mark.parametrize("key, bad", [("o", 0), ("c", 0), ("o", -5), ("c", 100.0), ("o", True), ("c", None)])
def test_invalid_prices_are_refused_with_the_bar_named(key, bad):
    dates, bars = bars_from([10_000] * 70)
    bars[60][key] = bad
    with pytest.raises(ValueError, match="Bar 60"):
        bt.simulate(dates, bars, "buy_hold", "example")


def test_a_fill_price_below_one_cent_is_refused_not_filled_at_zero():
    with pytest.raises(ValueError):
        bt.fill_price("sell", 1, "example")  # floor(0.999) would be 0
    assert bt.fill_price("buy", 1, "example") == 2 and bt.fill_price("sell", 1, "none") == 1
    assert bt.fill_price("sell", 2, "example") == 1


def test_an_unaffordable_entry_is_skipped_with_a_reason_and_the_rule_may_enter_later():
    """RSI 0 every day: the rule asks to buy each day; $10,000 first covers one share on index 51. Buy and hold decides
    once, on its start day, so its single skipped entry leaves it in cash for good."""
    closes = [3_000_000 - 40_000 * i for i in range(70)]
    dates, bars = bars_from(closes)
    rule, hold = (bt.simulate(dates, bars, r, "example") for r in ("rsi_threshold", "buy_hold"))
    assert [(s["index"], s["code"]) for s in rule["skipped"]] == [(50, "cash_below_one_share")]
    assert all(s["reason"] == bt.SKIP_REASON for s in rule["skipped"] + hold["skipped"])
    assert [(f["index"], f["shares"], f["price_cents"]) for f in rule["fills"]] == [(51, 1, 960_960)]
    assert hold["fills"] == [] and [s["index"] for s in hold["skipped"]] == [50]
    assert {(v["cash_cents"], v["shares"]) for v in hold["values"]} == {(1_000_000, 0)}
    check_accounting(rule, bars)
    check_accounting(hold, bars)


# ---- step 3: metrics ----

def sim_of(values, shares=None, fills=(), costs_paid=0):
    shares = shares or [0] * len(values)
    return {"values": [{"index": 49 + i, "date": f"d{49 + i:03}", "shares": s, "value_cents": v}
                       for i, (v, s) in enumerate(zip(values, shares))], "fills": list(fills),
            "costs_paid_cents": costs_paid}


def test_metrics_on_a_hand_worked_series():
    """Peak 1,100,000 on the first day after the start, a 10% fall to 990,000, the same 10% fall again from the same
    peak, a new high of 1,200,000 and a 10% fall from that: the earliest trough is reported, with its peak's first
    day."""
    v = [1_000_000, 1_100_000, 990_000, 1_100_000, 990_000, 1_200_000, 1_080_000]
    sim = sim_of(v, shares=[0, 1, 1, 0, 0, 1, 1], fills=[{"side": "buy"}, {"side": "sell"}, {"side": "buy"}],
                 costs_paid=123)
    m = bt.metrics(sim)
    assert m["total_return_pct"] == 8.0 and m["final_value_cents"] == 1_080_000
    assert m["max_drawdown_pct"] == 10.0
    assert m["max_drawdown"] == {"peak": {"index": 50, "date": "d050", "value_cents": 1_100_000},
                                 "trough": {"index": 51, "date": "d051", "value_cents": 990_000}}
    assert (m["buys"], m["sells"], m["evaluation_days"], m["days_invested"], m["costs_paid_cents"]) == (2, 1, 6, 4, 123)
    assert m["days_invested_pct"] == 66.67
    # daily changes +1/10, -1/10, +1/9, -1/10, +7/33, -1/10: mean 0.020539, squared deviations 0.094810 / 5, sqrt 13.770%
    changes = [Fraction(1, 10), Fraction(-1, 10), Fraction(1, 9), Fraction(-1, 10), Fraction(7, 33), Fraction(-1, 10)]
    assert m["daily_volatility_pct"] == 13.77 == round(statistics.stdev(changes) * 100, 2)
    assert m == ref_metrics(sim)


def test_flat_values_have_no_drawdown_and_no_volatility():
    m = bt.metrics(sim_of([1_000_000] * 21))
    assert (m["total_return_pct"], m["max_drawdown_pct"], m["max_drawdown"], m["daily_volatility_pct"],
            m["days_invested_pct"]) == (0.0, 0.0, None, 0.0, 0.0)


def test_a_steady_rise_has_no_drawdown():
    m = bt.metrics(sim_of([1_000_000 + 1_000 * i for i in range(30)]))
    assert m["max_drawdown"] is None and m["max_drawdown_pct"] == 0.0 and m["total_return_pct"] == 2.9


@pytest.mark.parametrize("ratio, expected", [
    (Fraction(5, 100_000), 0.01), (Fraction(-5, 100_000), -0.01),            # exactly half a hundredth: away from 0
    (Fraction(49_999, 1_000_000_000), 0.0), (Fraction(-4, 100_000), 0.0),    # rounds to zero, never "-0.0"
    (Fraction(44_281, 1_000_000), 4.43), (Fraction(-58_665, 1_000_000), -5.87), (Fraction(1), 100.0)])
def test_percentages_round_half_away_from_zero(ratio, expected):
    got = bt.pct(ratio)
    assert got == expected and str(got) != "-0.0"


@pytest.mark.parametrize("variance, expected", [
    (Fraction(0), 0.0), (Fraction(123, 10_000) ** 2, 1.23),
    (Fraction(125, 100_000) ** 2, 0.13),                                     # sqrt exactly 0.125%: half up
    (Fraction(125, 100_000) ** 2 - Fraction(1, 10 ** 30), 0.12),             # a hair below
    (Fraction(125, 100_000) ** 2 + Fraction(1, 10 ** 30), 0.13), (Fraction(2), 141.42)])
def test_the_square_root_and_its_rounding_are_exact(variance, expected):
    assert bt.sqrt_pct(variance) == expected
    with localcontext() as ctx:
        ctx.prec = 60
        assert dec_pct((Decimal(variance.numerator) / Decimal(variance.denominator)).sqrt()) == expected


@pytest.mark.parametrize("market, symbol", CASES, ids=CASE_IDS)
@pytest.mark.parametrize("costs", ["example", "none"])
def test_metrics_equal_the_independent_reference_for_every_symbol(market, symbol, costs):
    dates, bars = market["dates"], market["bars"][symbol]
    for last in sorted({bt.NEEDED_DAYS - 1, 100, len(bars) // 2 + 40, len(bars) - 1} & set(range(len(bars)))):
        for rule in RULES:
            sim = bt.simulate(dates[:last + 1], bars[:last + 1], rule, costs)
            m = bt.metrics(sim)
            assert m == ref_metrics(sim), (symbol, rule, last)
            vals = [v["value_cents"] for v in sim["values"]]
            floats = [b / a - 1 for a, b in zip(vals, vals[1:])]
            assert abs(m["daily_volatility_pct"] - statistics.stdev(floats) * 100) <= 0.005 + 1e-9


@pytest.mark.parametrize("market, symbol", CASES, ids=CASE_IDS)
def test_the_comparison_uses_the_same_days_and_the_exact_difference(market, symbol):
    dates, bars = market["dates"], market["bars"][symbol]
    for rule in bt.RULES:
        res = bt.run(dates, bars, rule, "example")["result"]
        s, b = res["strategy"], res["benchmark"]
        assert [(v["index"], v["date"]) for v in s["values"]] == [(v["index"], v["date"]) for v in b["values"]]
        assert s["metrics"]["evaluation_days"] == b["metrics"]["evaluation_days"] == len(bars) - 1 - 49
        gap = s["metrics"]["final_value_cents"] - b["metrics"]["final_value_cents"]
        with localcontext() as ctx:
            ctx.prec = 60
            assert res["difference_pp"] == dec_pct(Decimal(gap) / Decimal(1_000_000))
        # from the exact values, so it can differ from the difference of the two rounded returns by 0.01 at most
        diff = s["metrics"]["total_return_pct"] - b["metrics"]["total_return_pct"]
        assert abs(res["difference_pp"] - diff) <= 0.01 + 1e-9
        assert b["metrics"]["days_invested"] == b["metrics"]["evaluation_days"]  # filled at the Day 51 open


def test_the_approved_mockup_numbers():
    """docs/mockups/09: SYN-HLT1, SMA crossover, example costs, at Day 161."""
    market = paper_market.get("synthetic-b")
    res = bt.run(market["dates"][:161], market["bars"]["SYN-HLT1"][:161], "sma_cross", "example")["result"]
    s, b = res["strategy"]["metrics"], res["benchmark"]["metrics"]
    assert (s["final_value_cents"], s["total_return_pct"], b["final_value_cents"], b["total_return_pct"]) == \
        (1_044_281, 4.43, 1_102_960, 10.3)
    assert res["difference_pp"] == -5.87
    assert (s["max_drawdown_pct"], s["max_drawdown"]["peak"]["date"], s["max_drawdown"]["trough"]["date"]) == \
        (10.51, "2025-05-12", "2025-06-09")
    assert (b["max_drawdown_pct"], b["max_drawdown"]["trough"]["date"]) == (10.73, "2025-07-03")
    assert (s["daily_volatility_pct"], b["daily_volatility_pct"]) == (0.96, 1.63)
    assert (s["days_invested"], s["evaluation_days"], s["costs_paid_cents"], b["costs_paid_cents"]) == \
        (49, 111, 3091, 1089)
    assert (s["buys"], s["sells"], b["buys"], b["sells"]) == (2, 1, 1, 0)
    h = res["halves"]
    assert h["midpoint_index"] == 104  # Day 105
    assert [(h[k]["strategy"]["metrics"]["total_return_pct"], h[k]["benchmark"]["metrics"]["total_return_pct"])
            for k in ("earlier", "later")] == [(-1.75, 2.86), (9.14, 7.18)]


# ---- step 3: halves ----

def test_halves_appear_only_with_forty_evaluation_days_each():
    b_market, a_market = paper_market.get("synthetic-b"), paper_market.get("synthetic-a")
    dates, bars = b_market["dates"], b_market["bars"]["SYN-HLT1"]
    assert bt.run(dates[:129], bars[:129], "sma_cross", "example")["result"]["halves"] is None  # L = 128
    h = bt.run(dates[:130], bars[:130], "sma_cross", "example")["result"]["halves"]           # L = 129
    assert h["midpoint_index"] == 89
    assert [h[k]["strategy"]["metrics"]["evaluation_days"] for k in ("earlier", "later")] == [40, 40]
    for symbol in a_market["symbols"]:
        assert bt.run(a_market["dates"], a_market["bars"][symbol], "rsi_threshold", "none")["result"]["halves"] is None
    for last in (129, 130, 131, 200, 249):
        h = bt.halves(dates[:last + 1], bars[:last + 1], "sma_cross", "none")
        mid = 49 + (last - 49) // 2
        assert h["midpoint_index"] == mid and mid - 49 >= 40 and last - mid >= 40
        assert h["earlier"]["strategy"]["last_index"] == mid and h["later"]["strategy"]["last_index"] == last


LONG = [(m, s) for m, s in CASES if len(m["dates"]) > 130]


@pytest.mark.parametrize("market, symbol", LONG, ids=[s for _, s in LONG])
def test_each_half_is_an_independent_run_from_ten_thousand_dollars(market, symbol):
    dates, bars = market["dates"], market["bars"][symbol]
    for rule in bt.RULES:
        for costs in ("example", "none"):
            res = bt.run(dates, bars, rule, costs)["result"]
            h, mid = res["halves"], res["halves"]["midpoint_index"]
            for half, start in (("earlier", 49), ("later", mid)):
                for side, r in (("strategy", rule), ("benchmark", "buy_hold")):
                    got = h[half][side]
                    assert got["values"][0]["index"] == start
                    assert (got["values"][0]["cash_cents"], got["values"][0]["shares"],
                            got["values"][0]["value_cents"]) == (1_000_000, 0, 1_000_000)
                    assert all(f["index"] > start for f in got["fills"])
                    last = got["last_index"]
                    sim = {k: v for k, v in got.items() if k != "metrics"}
                    assert sim == ref_run(dates[:last + 1], bars[:last + 1], r, costs, start=start)
                    assert got["metrics"] == ref_metrics(sim)
                    check_accounting(sim, bars)
            # the earlier half shares the full run's start, so it is exactly the full run's prefix
            for side in ("strategy", "benchmark"):
                assert h["earlier"][side]["values"] == res[side]["values"][:mid - 48]
                assert h["earlier"][side]["fills"] == [f for f in res[side]["fills"] if f["index"] <= mid]


def cross_at_90():
    """Flat at 10,000 (equal averages) to index 89, rising from index 90: the only cross up is on index 90."""
    closes = [10_000] * 90 + [10_000 + 50 * k for k in range(1, 61)]
    above = bt.signals(closes)["above"]
    assert [i for i in range(50, 150) if above[i] and not above[i - 1]] == [90]
    return bars_from(closes)


def test_a_cross_on_the_later_halfs_start_day_is_its_own_decision():
    dates, bars = cross_at_90()
    last = 2 * 90 - 49  # makes the midpoint 90
    h = bt.halves(dates[:last + 1], bars[:last + 1], "sma_cross", "none")
    assert h["midpoint_index"] == 90
    assert [(f["signal_index"], f["index"], f["side"]) for f in h["later"]["strategy"]["fills"]] == [(90, 91, "buy")]
    assert h["earlier"]["strategy"]["unacted_signal"] == {"index": 90, "date": "d090", "side": "buy"}


def test_the_later_half_inherits_no_position_and_presumes_no_entry():
    """With the midpoint at 95 the full run has held shares since 91, but the averages are already apart on 94 and 95:
    the later half starts in cash and, with no fresh cross, stays in cash."""
    dates, bars = cross_at_90()
    last = 2 * 95 - 49
    res = bt.run(dates[:last + 1], bars[:last + 1], "sma_cross", "none")["result"]
    assert res["halves"]["midpoint_index"] == 95
    assert res["strategy"]["values"][95 - 49]["shares"] > 0
    later = res["halves"]["later"]["strategy"]
    assert later["fills"] == [] and {(v["cash_cents"], v["shares"]) for v in later["values"]} == {(1_000_000, 0)}
    assert later["metrics"]["days_invested"] == 0 and later["metrics"]["total_return_pct"] == 0.0


@pytest.mark.parametrize("rule", RULES)
def test_changing_later_prices_changes_nothing_earlier_in_a_later_start_run(rule):
    market = paper_market.get("synthetic-b")
    dates = market["dates"]
    rng = random.Random(20261031)
    for symbol in ("SYN-HLT1", "SYN-ENR1", "SYN-CON1"):
        bars = market["bars"][symbol]
        base = bt.simulate(dates, bars, rule, "example", start=149)
        for t in (160, 200, 230):
            changed = copy.deepcopy(bars)
            for b in changed[t + 1:]:
                b["o"], b["c"] = rng.randint(500, 50_000), rng.randint(500, 50_000)
            other = bt.simulate(dates, changed, rule, "example", start=149)
            assert other["values"][:t - 148] == base["values"][:t - 148]
            decided = lambda r: [(f["signal_index"], f["side"]) for f in r["fills"] + r["skipped"] if f["signal_index"] <= t]
            assert decided(other) == decided(base)


def test_results_with_metrics_and_halves_are_repeatable():
    market = paper_market.get("synthetic-b")
    dates, bars = market["dates"], market["bars"]["SYN-CON1"]
    before = copy.deepcopy(bars)
    runs = {json.dumps(bt.run(dates, bars, "sma_cross", "example"), sort_keys=True) for _ in range(3)}
    assert len(runs) == 1 and bars == before
    assert '"halves": {' in runs.pop()


def test_metrics_equal_the_reference_at_window_ends_spread_over_every_residue():
    """Brief section 7 asks for every possible L: each symbol takes every 10th L from its own offset, so together the
    14 symbols cover every last day modulo 10 (scripts in the P5 evidence folder ran every L once)."""
    covered = set()
    for k, (market, symbol) in enumerate(CASES):
        dates, bars = market["dates"], market["bars"][symbol]
        for last in range(bt.NEEDED_DAYS - 1 + k % 10, len(bars), 10):
            covered.add(last % 10)
            for rule in RULES:
                sim = bt.simulate(dates[:last + 1], bars[:last + 1], rule, "example" if k % 2 else "none")
                assert bt.metrics(sim) == ref_metrics(sim), (symbol, rule, last)
    assert covered == set(range(10))
