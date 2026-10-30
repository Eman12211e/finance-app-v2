"""P5 step 2: the backtesting engine (services/backtest.py) against docs/P5_BRIEF.md section 3, a separate reference
written here with exact integer and fraction arithmetic, and the accounting, start, boundary and no-look-ahead rules.
Offline: only the fixed synthetic scenario files are read."""
import copy
import json
import math
import os
import random
from fractions import Fraction

import pytest

from services import backtest as bt
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
                                    "open_cents": o, "price_cents": p,
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

@pytest.mark.parametrize("fast, slow, holding, expected", [
    ([10.0, 10.0], [10.0, 10.0], False, None),        # equal on both days: not above, no cross
    ([10.0, 10.0001], [10.0, 10.0], False, "buy"),    # equal, then above: a cross up
    ([9.0, 11.0], [10.0, 10.0], False, "buy"),
    ([9.0, 11.0], [10.0, 10.0], True, None),          # a cross up while holding does nothing
    ([10.1, 10.0], [10.0, 10.0], True, "sell"),       # above, then equal: a cross down
    ([11.0, 9.0], [10.0, 10.0], False, None),         # a cross down while in cash does nothing
    ([11.0, 12.0], [10.0, 10.0], False, None),        # above on both days: no cross, so no presumed entry
    ([None, 11.0], [None, 10.0], False, None),        # no average yesterday: no crossing can be seen
    ([9.0, 11.0], [None, 10.0], False, None)])
def test_crossing_boundaries(fast, slow, holding, expected):
    assert bt.decide("sma_cross", 1, 0, holding, {"fast": fast, "slow": slow, "rsi": [None, None]}) == expected


@pytest.mark.parametrize("rsi, holding, expected", [
    (30.0, False, None), (29.999999, False, "buy"), (0.0, False, "buy"), (25.0, True, None),
    (70.0, True, None), (70.000001, True, "sell"), (100.0, True, "sell"), (75.0, False, None),
    (50.0, False, None), (None, False, None), (None, True, None)])
def test_rsi_threshold_boundaries_are_strict(rsi, holding, expected):
    assert bt.decide("rsi_threshold", 0, 0, holding, {"fast": [None], "slow": [None], "rsi": [rsi]}) == expected


def test_buy_and_hold_decides_once_on_its_start_day():
    series = {"fast": [None] * 3, "slow": [None] * 3, "rsi": [None] * 3}
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
                             "price_cents": 2_002_000, "reason": "The cash did not cover one share at this price."}]
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
