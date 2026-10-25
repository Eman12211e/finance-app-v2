"""Paper Trading Lab market data: the synthetic scenario is reproducible, well formed, fictional and labelled,
and callers can never read past the current replay day."""
import os
import sys
from datetime import date

import pytest

from services import paper_market
from services.errors import InvalidRequest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def scenario():
    return paper_market.get("synthetic-a")


def test_committed_scenario_matches_the_fixed_seed_generator():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import build_synthetic_scenario
    assert build_synthetic_scenario.build() == scenario()
    assert scenario()["generator"]["seed"] == build_synthetic_scenario.SEED


def test_scenario_is_labelled_synthetic_with_fictional_symbols():
    m = scenario()
    assert m["kind"] == "synthetic" and m["timeframe"] == "1D"
    assert "Not real market data, not live quotes" in m["notice"]
    assert all(s.startswith("SAMPLE-") and "(fictional)" in v["name"] for s, v in m["symbols"].items())


def test_bars_are_valid_ohlcv_in_integer_cents():
    m = scenario()
    for symbol, bars in m["bars"].items():
        assert len(bars) == len(m["dates"]) == 120, symbol
        for b in bars:
            assert set(b) == {"o", "h", "l", "c", "v"}
            assert all(isinstance(b[k], int) and not isinstance(b[k], bool) and b[k] > 0 for k in b)
            assert b["l"] <= min(b["o"], b["c"]) <= max(b["o"], b["c"]) <= b["h"], (symbol, b)


def test_dates_are_increasing_business_days():
    days = [date.fromisoformat(d) for d in scenario()["dates"]]
    assert days == sorted(set(days)) and all(d.weekday() < 5 for d in days)


@pytest.mark.parametrize("day", [0, 1, 57, 119])
def test_bars_until_never_returns_a_later_bar(day):
    m = scenario()
    got = paper_market.bars_until(m, day)
    assert len(got["dates"]) == day + 1 and got["dates"][-1] == m["dates"][day]
    for symbol, bars in got["bars"].items():
        assert len(bars) == day + 1 and bars[-1] == m["bars"][symbol][day]


@pytest.mark.parametrize("day", [-1, 120, 10_000])
def test_bars_until_rejects_days_outside_the_scenario(day):
    with pytest.raises(InvalidRequest):
        paper_market.bars_until(scenario(), day)


def test_unknown_scenario_is_rejected():
    with pytest.raises(InvalidRequest):
        paper_market.get("../config")
