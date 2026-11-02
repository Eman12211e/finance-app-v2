"""Test a strategy endpoint (P5 step 4): POST /api/backtest/run. The response against the engine and the independent
reference in test_backtest.py, insufficient history, the current-day limit, signed sessions, validation, fuzz, size
limit and read-only behaviour."""
import copy
import functools
import json
import os
import random

import pytest

from services import backtest as bt
from services import indicators as ind
from services import paper_engine as eng
from services import paper_market
from tests.test_backtest import check_accounting, ref_metrics, ref_run

ROOT = os.path.join(os.path.dirname(__file__), "..")
URL = "/api/backtest/run"


@functools.lru_cache(maxsize=None)
def _signed_state(scenario, day):
    s = eng.new_state(scenario)
    for d in range(day):
        s = eng.advance(s, d)
    return s


def state_on(day, scenario="synthetic-b"):
    """A signed session advanced to simulated day `day` (0-based), with no orders; a fresh copy each call."""
    return copy.deepcopy(_signed_state(scenario, day))


def ask(client, state, symbol="SYN-HLT1", preset="sma_cross", costs="example", **extra):
    return client.post(URL, json={"state": state, "symbol": symbol, "preset": preset, "costs": costs} | extra)


def data(resp):
    env = resp.get_json()
    assert resp.status_code == 200 and env["ok"] and env["source"] is None and env["error"] is None, env
    return env["data"]


def error(resp, code="INVALID_REQUEST", status=400):
    env = resp.get_json()
    assert resp.status_code == status and env["ok"] is False and env["data"] is None, (resp.status_code, env)
    assert env["error"]["code"] == code, env
    return env["error"]["message"]


def market(scenario="synthetic-b"):
    return paper_market.get(scenario)


# ---- valid requests ----

def test_the_mockup_request_returns_the_approved_numbers_and_shape(client):
    d = data(ask(client, state_on(160)))
    m = market()
    assert (d["symbol"], d["preset"], d["costs"], d["date"]) == ("SYN-HLT1", "sma_cross", "example", m["dates"][160])
    assert (d["needed_days"], d["available_days"]) == (70, 161)
    assert d["window"] == {"start_index": 49, "start_date": m["dates"][49], "last_index": 160,
                           "last_date": m["dates"][160], "evaluation_days": 111}
    assert d["notice"] == m["notice"] and d["education"].startswith("This is a hypothetical test")
    r = d["result"]
    assert set(r) == {"strategy", "benchmark", "difference_pp", "unacted_signal", "halves", "dates", "bars",
                      "indicators"}
    assert r["bars"] == [{"time": t, "o": x["o"], "h": x["h"], "l": x["l"], "c": x["c"]}
                         for t, x in zip(m["dates"][:161], m["bars"]["SYN-HLT1"][:161])]  # stops at today
    s, b = r["strategy"], r["benchmark"]
    assert (s["metrics"]["total_return_pct"], b["metrics"]["total_return_pct"], r["difference_pp"]) == (4.43, 10.3, -5.87)
    assert [(f["index"], f["side"], f["shares"]) for f in s["fills"]] == [(79, "buy", 94), (113, "sell", 94),
                                                                         (146, "buy", 93)]
    assert s["end"]["shares"] == 93 and b["end"]["shares"] > 0
    assert s["values"][0] == {"time": m["dates"][49], "value_cents": 1_000_000}
    assert [v["time"] for v in s["values"]] == [v["time"] for v in b["values"]] == m["dates"][49:161]
    assert r["dates"] == m["dates"][:161]
    closes = [x["c"] for x in m["bars"]["SYN-HLT1"][:161]]
    assert r["indicators"] == [{"type": "sma", "period": 20, "series": ind.compute("sma", 20, closes)},
                               {"type": "sma", "period": 50, "series": ind.compute("sma", 50, closes)}]
    h = r["halves"]
    assert (h["midpoint_index"], h["midpoint_date"]) == (104, m["dates"][104])
    assert h["earlier"]["window"]["evaluation_days"] == 55 and h["later"]["window"]["evaluation_days"] == 56
    assert [(h[k]["strategy"]["metrics"]["total_return_pct"], h[k]["benchmark"]["metrics"]["total_return_pct"])
            for k in ("earlier", "later")] == [(-1.75, 2.86), (9.14, 7.18)]
    assert "values" not in h["earlier"]["strategy"]  # the halves are a table, not a chart


@pytest.mark.parametrize("preset, costs", [(p, c) for p in bt.RULES for c in bt.SLIPPAGE_BPS])
def test_every_symbol_preset_and_cost_setting_equals_the_independent_reference(client, preset, costs):
    for scenario, day in (("synthetic-a", 119), ("synthetic-b", 249), ("synthetic-b", 130)):
        m = market(scenario)
        for symbol in m["symbols"]:
            d = data(ask(client, state_on(day, scenario), symbol, preset, costs))
            dates, bars = m["dates"][:day + 1], m["bars"][symbol][:day + 1]
            for side, rule in (("strategy", preset), ("benchmark", "buy_hold")):
                ref = ref_run(dates, bars, rule, costs)
                check_accounting(ref, bars)
                got = d["result"][side]
                assert got["fills"] == ref["fills"] and got["skipped"] == ref["skipped"]
                assert got["values"] == [{"time": v["date"], "value_cents": v["value_cents"]} for v in ref["values"]]
                assert got["metrics"] == ref_metrics(ref)
            assert d["result"]["unacted_signal"] == ref_run(dates, bars, preset, costs)["unacted_signal"]
            assert (d["result"]["halves"] is None) == (day - 49 < 80)
            if d["result"]["halves"]:
                mid = d["result"]["halves"]["midpoint_index"]
                later = ref_run(dates, bars, preset, costs, start=mid)
                assert d["result"]["halves"]["later"]["strategy"]["fills"] == later["fills"]
                assert d["result"]["halves"]["later"]["strategy"]["metrics"] == ref_metrics(later)


def test_rsi_rule_returns_the_rsi_line(client):
    d = data(ask(client, state_on(120), "SYN-ENR1", "rsi_threshold", "none"))
    closes = [x["c"] for x in market()["bars"]["SYN-ENR1"][:121]]
    assert d["result"]["indicators"] == [{"type": "rsi", "period": 14, "series": ind.compute("rsi", 14, closes)}]


# ---- history and the current day ----

def test_not_enough_history_returns_a_null_result_with_the_counts(client):
    for day in (0, 1, 49, 68):
        d = data(ask(client, state_on(day)))
        assert (d["result"], d["window"], d["needed_days"], d["available_days"]) == (None, None, 70, day + 1)
        assert d["date"] == market()["dates"][day]
    d = data(ask(client, state_on(69)))
    assert d["window"]["evaluation_days"] == 20 and d["result"]["halves"] is None


def test_halves_start_at_day_130(client):
    assert data(ask(client, state_on(128)))["result"]["halves"] is None
    h = data(ask(client, state_on(129)))["result"]["halves"]
    assert h["midpoint_index"] == 89 and h["later"]["strategy"]["metrics"]["evaluation_days"] == 40


@pytest.mark.parametrize("day", [69, 90, 164, 200])
def test_nothing_after_the_session_day_is_used_or_returned(client, day):
    d = data(ask(client, state_on(day), "SYN-CON1"))
    m = market()
    assert d["window"]["last_date"] == d["date"] == m["dates"][day] and len(d["result"]["dates"]) == day + 1
    assert len(d["result"]["bars"]) == day + 1 and d["result"]["bars"][-1]["time"] == m["dates"][day]
    assert all(f["index"] <= day for side in ("strategy", "benchmark") for f in d["result"][side]["fills"])
    # the whole answer equals a run on bars that stop at today, so later prices cannot reach it
    assert d["result"]["strategy"]["metrics"] == bt.run(m["dates"][:day + 1], m["bars"]["SYN-CON1"][:day + 1],
                                                        "sma_cross", "example")["result"]["strategy"]["metrics"]


def test_a_signal_on_the_current_day_is_reported_not_filled(client):
    d = data(ask(client, state_on(164), "SYN-CON1"))
    assert d["result"]["unacted_signal"] == {"index": 164, "date": market()["dates"][164], "side": "sell"}


def test_the_same_request_gives_byte_identical_json(client):
    state = state_on(200)
    first, second = (ask(client, state, "SYN-IND2", "rsi_threshold").get_data() for _ in range(2))
    assert first == second
    assert json.loads(first)["data"]["result"]["halves"] is not None


# ---- sessions ----

def test_a_tampered_session_is_rejected(client):
    state = state_on(80)
    state["day"] = 200  # peek ahead without a valid signature
    error(ask(client, state), "INVALID_STATE")
    state = state_on(80)
    state["sig"] = "0" * len(state["sig"])
    error(ask(client, state), "INVALID_STATE")


@pytest.mark.parametrize("bad_state", [None, "", "x", 5, True, [], {}, {"sig": "a"},
                                       {"schema": 1, "scenario": "synthetic-b"}])
def test_a_malformed_or_missing_session_is_rejected(client, bad_state):
    error(ask(client, bad_state), "INVALID_STATE")
    body = {"symbol": "SYN-HLT1", "preset": "sma_cross", "costs": "none"}
    error(client.post(URL, json=body), "INVALID_STATE")


def test_the_request_never_changes_the_session(client, monkeypatch):
    state = state_on(150)
    before = copy.deepcopy(state)
    for name in ("confirm", "cancel", "advance", "new_state", "_sign"):
        monkeypatch.setattr(eng, name, lambda *a, **k: pytest.fail("a backtest must not change a session"))
    data(ask(client, state))
    assert state == before


def test_a_session_with_orders_and_positions_is_unchanged_and_ignored(client):
    """The test uses fictional $10,000 of its own; the learner's real practice orders do not enter it."""
    plain = state_on(100)
    traded, duplicate = eng.confirm(state_on(99), {"id": "order-0001", "symbol": "SYN-HLT1", "side": "buy",
                                                    "shares": 30})
    traded = eng.advance(traded, 99)  # filled at the Day 101 open, like plain's day
    assert duplicate is False and eng.view(traded)["portfolio"] != eng.view(plain)["portfolio"]
    before = copy.deepcopy(traded)
    assert data(ask(client, traded))["result"] == data(ask(client, plain))["result"]
    assert traded == before


# ---- validation ----

@pytest.mark.parametrize("raw", [b"", b"not json", b"[]", b"5", b'"text"', b"null", b"{"])
def test_the_body_must_be_a_json_object(client, raw):
    error(client.post(URL, data=raw, content_type="application/json"))


def test_an_oversized_request_is_refused(client):
    error(ask(client, state_on(80), padding="x" * 70_000), "REQUEST_TOO_LARGE", 413)


def test_get_is_not_allowed(client):
    assert client.get(URL).status_code == 405


@pytest.mark.parametrize("extra", [{"padding": 1}, {"start": 10}, {"days": 300}, {"cash": 10**9}, {"STATE": {}}])
def test_unknown_fields_are_refused(client, extra):
    assert "only state, symbol, preset and costs" in error(ask(client, state_on(80), **extra))


@pytest.mark.parametrize("symbol", ["AAPL", "SAMPLE-A", "syn-hlt1", "", "../config", 7, None, True, ["SYN-HLT1"], {}])
def test_unknown_symbols_are_refused(client, symbol):
    assert "symbol" in error(ask(client, state_on(80), symbol=symbol))


@pytest.mark.parametrize("preset", ["buy_hold", "ema_cross", "SMA_CROSS", "", None, True, 1, ["sma_cross"], {}])
def test_unknown_presets_are_refused(client, preset):
    assert "Choose a rule" in error(ask(client, state_on(80), preset=preset))


@pytest.mark.parametrize("costs", ["cheap", "Example", "", None, False, 0, 10, ["none"], {"none": 1}])
def test_unknown_cost_settings_are_refused(client, costs):
    assert "cost setting" in error(ask(client, state_on(80), costs=costs))


def test_a_scenario_ticker_from_the_other_market_is_refused(client):
    assert "symbol" in error(ask(client, state_on(80, "synthetic-a"), symbol="SYN-HLT1"))


def test_seeded_fuzz_of_malformed_requests_never_returns_500(client):
    rng = random.Random(20261031)
    state = state_on(90)
    atoms = [None, True, False, 0, -1, 1.5, "", "sma_cross", "rsi_threshold", "buy_hold", "example", "none",
             "SYN-HLT1", [], {}, "x" * 60, {"day": 300}]

    def junk(depth=0):
        if depth > 2 or rng.random() < 0.5:
            return rng.choice(atoms)
        if rng.random() < 0.5:
            return [junk(depth + 1) for _ in range(rng.randint(0, 4))]
        keys = rng.sample(["state", "symbol", "preset", "costs", "day", "sig", "extra"], rng.randint(0, 3))
        return {k: junk(depth + 1) for k in keys}

    codes = set()
    for _ in range(400):
        body = {"state": rng.choice([state, junk()]), "symbol": rng.choice(["SYN-HLT1", junk()]),
                "preset": rng.choice(["sma_cross", "rsi_threshold", junk()]),
                "costs": rng.choice(["example", "none", junk()])}
        if rng.random() < 0.2:
            body[rng.choice(["extra", "day", "x"])] = junk()
        if rng.random() < 0.1:
            body.pop(rng.choice(list(body)))
        resp = client.post(URL, json=body)
        env = resp.get_json()
        assert resp.status_code in (200, 400), (resp.status_code, body)
        assert env["ok"] is (resp.status_code == 200)
        codes.add(env["error"]["code"] if env["error"] else "OK")
    assert codes == {"OK", "INVALID_REQUEST", "INVALID_STATE"}  # the fuzz reached every outcome


def test_an_unexpected_failure_is_logged_and_answered_without_details(client, monkeypatch):
    monkeypatch.setattr(bt, "run", lambda *a: 1 / 0)
    assert error(ask(client, state_on(80)), "INTERNAL_ERROR", 500) == "Something went wrong. Please try again."


# ---- isolation ----

def test_the_route_reads_bars_only_through_market_bars():
    with open(os.path.join(ROOT, "routes", "backtest.py"), encoding="utf-8") as f:
        source = f.read()
    engine_calls = {w.split("(")[0] for w in source.split("paper_engine.")[1:]}
    assert engine_calls == {"market_bars"} and "paper_market" not in source
    with open(os.path.join(ROOT, "services", "paper_engine.py"), encoding="utf-8") as f:
        assert "backtest" not in f.read()
