"""Analysis Toolbox maths (P4 step 2): worked examples, edge cases, "Not enough data", no look-ahead, and the weekly
rules (completed weeks only, Partial Week, Final Short Week). See docs/P4_BRIEF.md."""
import os
from datetime import date

import pytest

from services import indicators as ind
from services import paper_market

ROOT = os.path.join(os.path.dirname(__file__), "..")


def market():
    return paper_market.get("synthetic-b")


def closes(symbol="SYN-TEC1"):
    return [b["c"] for b in market()["bars"][symbol]]


def weeks_on(day, symbol="SYN-TEC1"):
    """Weekly bars as the server will build them on simulated day `day` (0-based): daily bars up to today only."""
    m = market()
    return ind.weekly(m["dates"][:day + 1], m["bars"][symbol][:day + 1], day == paper_market.last_day(m))


def day_of(iso):
    return market()["dates"].index(iso)


# ---- worked examples, checked by hand ----

def test_sma_worked_example():
    assert ind.sma([1, 2, 3, 4, 5, 6], 3) == [None, None, 2, 3, 4, 5]


def test_ema_is_seeded_with_the_sma_then_weights_recent_values():
    assert ind.ema([1, 2, 3, 4, 5], 3) == [None, None, 2, 3, 4]  # k = 0.5: 4*.5 + 2*.5 = 3, then 5*.5 + 3*.5 = 4
    assert ind.ema([None, None, 1, 2, 3, 4, 5], 3) == [None, None, None, None, 2, 3, 4]  # starts where the input does


def test_rsi_worked_example_with_wilder_smoothing():
    # changes +1, +1, -1; first averages over 2 changes: gain 1, loss 0 -> 100; then gain .5, loss .5 -> 50
    assert ind.rsi([1, 2, 3, 2], 2) == [None, None, 100.0, 50.0]


def test_macd_of_a_straight_line_is_constant_and_its_histogram_zero():
    # fast EMA lags a slope-1 line by (2-1)/2, slow by (3-1)/2, so MACD = 0.5 once both exist
    out = ind.macd([1, 2, 3, 4, 5, 6], fast=2, slow=3, signal=2)
    assert out["macd"] == [None, None, 0.5, 0.5, 0.5, 0.5]
    assert out["signal"] == [None, None, None, 0.5, 0.5, 0.5]
    assert out["histogram"] == [None, None, None, 0.0, 0.0, 0.0]


# ---- constant, rising and falling prices ----

@pytest.mark.parametrize("kind,period", [("sma", 20), ("sma", 50), ("ema", 12), ("ema", 26)])
def test_averages_of_constant_prices_equal_the_price(kind, period):
    values = ind.compute(kind, period, [12345] * 60)[kind]
    assert all(v is None for v in values[:period - 1])
    assert set(values[period - 1:]) == {123.45}


def test_rsi_constant_rising_falling():
    assert set(ind.compute("rsi", 14, [5000] * 30)["rsi"][14:]) == {50.0}  # no gains and no losses
    assert set(ind.compute("rsi", 14, list(range(5000, 5030)))["rsi"][14:]) == {100.0}
    assert set(ind.compute("rsi", 14, list(range(5030, 5000, -1)))["rsi"][14:]) == {0.0}


def test_macd_constant_rising_falling():
    flat = ind.compute("macd", (12, 26, 9), [5000] * 60)
    for name in ("macd", "signal", "histogram"):
        assert {v for v in flat[name] if v is not None} == {0.0}, name  # exactly 0, never -0.0
        assert all(str(v) != "-0.0" for v in flat[name])
    rising = ind.compute("macd", (12, 26, 9), [5000 + 10 * i for i in range(60)])["macd"]
    falling = ind.compute("macd", (12, 26, 9), [9000 - 10 * i for i in range(60)])["macd"]
    assert rising[-1] > 0 > falling[-1]


# ---- "Not enough data": exact thresholds, nothing estimated ----

@pytest.mark.parametrize("kind,period,name,first", [
    ("sma", 20, "sma", 19), ("sma", 50, "sma", 49), ("ema", 12, "ema", 11), ("ema", 26, "ema", 25),
    ("rsi", 14, "rsi", 14), ("macd", (12, 26, 9), "macd", 25), ("macd", (12, 26, 9), "signal", 33),
    ("macd", (12, 26, 9), "histogram", 33),
])
def test_first_value_appears_exactly_when_enough_history_exists(kind, period, name, first):
    data = closes()
    short = ind.compute(kind, period, data[:first])[name]  # one close too few
    assert short == [None] * first
    enough = ind.compute(kind, period, data[:first + 1])[name]
    assert enough[:first] == [None] * first and enough[first] is not None


def test_empty_and_tiny_inputs_give_no_values():
    for kind, periods in ind.PRESETS.items():
        for period in periods:
            for series in ind.compute(kind, period, []).values():
                assert series == []
            for series in ind.compute(kind, period, [5000]).values():
                assert series == [None]


def test_only_offered_presets_are_computed():
    for kind, period in [("sma", 7), ("ema", 20), ("rsi", 9), ("macd", (5, 35, 5)), ("bollinger", 20)]:
        with pytest.raises(ValueError):
            ind.compute(kind, period, closes())


# ---- no look-ahead: a value never changes when later prices are added ----

@pytest.mark.parametrize("kind,period", [(k, p) for k, ps in ind.PRESETS.items() for p in ps])
def test_values_up_to_any_day_equal_the_full_history_cut_at_that_day(kind, period):
    data = closes()
    full = ind.compute(kind, period, data)
    for day in range(len(data)):
        cut = ind.compute(kind, period, data[:day + 1])
        for name, values in cut.items():
            assert values == full[name][:day + 1], (name, day)


# ---- weekly bars and the weekly rules ----

def test_weekly_bars_aggregate_the_daily_bars_up_to_today():
    m = market()
    day = day_of("2025-08-14")
    weeks = weeks_on(day)
    by_week = {}
    for d, b in zip(m["dates"][:day + 1], m["bars"]["SYN-TEC1"][:day + 1]):
        by_week.setdefault(date.fromisoformat(d).isocalendar()[:2], []).append((d, b))
    assert len(weeks) == len(by_week)
    for w, days in zip(weeks, by_week.values()):
        bars = [b for _, b in days]
        assert w["time"] == days[0][0] and w["end"] == days[-1][0] and w["days"] == len(days)
        assert (w["o"], w["c"]) == (bars[0]["o"], bars[-1]["c"])
        assert w["h"] == max(b["h"] for b in bars) and w["l"] == min(b["l"] for b in bars)
        assert w["v"] == sum(b["v"] for b in bars)
    assert weeks[-1]["end"] == "2025-08-14"  # nothing after today


def test_short_first_week_is_complete():
    first = weeks_on(day_of("2025-01-10"))[0]
    assert (first["time"], first["end"], first["days"], first["status"]) == ("2025-01-02", "2025-01-03", 2, "complete")


def test_unfinished_week_is_partial_and_left_out_of_completed_weeks():
    for iso in ("2025-08-11", "2025-08-12", "2025-08-13", "2025-08-14"):  # Monday to Thursday
        weeks = weeks_on(day_of(iso))
        assert [w["status"] for w in weeks].count("partial") == 1 and weeks[-1]["status"] == "partial"
        assert ind.completed(weeks)[-1]["end"] == "2025-08-08"
    friday = weeks_on(day_of("2025-08-15"))
    assert friday[-1]["status"] == "complete" and ind.completed(friday)[-1]["end"] == "2025-08-15"


@pytest.mark.parametrize("kind,period", [(k, p) for k, ps in ind.PRESETS.items() for p in ps])
def test_weekly_indicators_ignore_the_partial_week_and_change_only_when_a_week_completes(kind, period):
    def weekly_values(day):
        return ind.compute(kind, period, [w["c"] for w in ind.completed(weeks_on(day))])

    last_friday = weekly_values(day_of("2025-08-08"))
    for iso in ("2025-08-11", "2025-08-12", "2025-08-13", "2025-08-14"):
        assert weekly_values(day_of(iso)) == last_friday, iso  # the Partial Week's days change nothing
    assert weekly_values(day_of("2025-08-15")) != last_friday  # the week completed on Friday


def test_completed_weeks_never_change_on_later_days():
    m = market()
    final = ind.completed(weeks_on(paper_market.last_day(m)))
    for day in range(paper_market.last_day(m) + 1):
        done = ind.completed(weeks_on(day))
        assert done == final[:len(done)], day


def test_final_short_week_completes_only_on_the_final_day():
    m = market()
    last = paper_market.last_day(m)
    assert m["dates"][last] == "2025-12-17" and date(2025, 12, 17).weekday() == 2  # synthetic-b ends on a Wednesday
    before = weeks_on(last - 1)
    assert before[-1]["status"] == "partial" and before[-1]["days"] == 2  # Mon 15 and Tue 16 Dec
    assert ind.completed(before)[-1]["end"] == "2025-12-12"
    final = weeks_on(last)
    assert final[-1]["status"] == "final_short" and final[-1]["days"] == 3 and final[-1]["end"] == "2025-12-17"
    assert ind.completed(final)[-1] == final[-1]  # included in the weekly calculations from the final day
    for kind, periods in ind.PRESETS.items():
        for period in periods:
            on_final = ind.compute(kind, period, [w["c"] for w in ind.completed(final)])
            before_values = ind.compute(kind, period, [w["c"] for w in ind.completed(before)])
            for name in on_final:
                assert on_final[name][:-1] == before_values[name], (kind, name)  # one more completed week, nothing else


def test_weekly_not_enough_data_on_day_161():
    done = ind.completed(weeks_on(day_of("2025-08-14")))
    assert len(done) == 32
    c = [w["c"] for w in done]
    assert ind.compute("sma", 20, c)["sma"][-1] is not None and ind.compute("sma", 50, c)["sma"][-1] is None
    assert ind.compute("rsi", 14, c)["rsi"][-1] is not None
    out = ind.compute("macd", (12, 26, 9), c)
    assert out["macd"][-1] is not None and out["signal"][-1] is None and out["histogram"][-1] is None  # 7 of 9


# ---- educational only: the trading engine never uses these values ----

def test_engine_and_trading_routes_do_not_use_indicators():
    for parts in (("services", "paper_engine.py"), ("services", "paper_market.py"), ("routes", "paper.py")):
        with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
            assert "indicators" not in f.read(), parts
