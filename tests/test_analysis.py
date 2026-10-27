"""Analysis endpoint (P4 step 3): POST /api/analysis/indicators. Valid daily and weekly requests, every preset,
"Not enough data", tampered and malformed sessions, no future data, completed-week and Final Short Week handling,
invalid combinations, and read-only behaviour."""
import copy
import functools
from datetime import date

import pytest

from services import indicators as ind
from services import paper_engine as eng
from services import paper_market

ALL_DAILY = [{"type": "sma", "period": 20}, {"type": "ema", "period": 12}, {"type": "rsi", "period": 14},
             {"type": "macd", "period": [12, 26, 9]}]
OTHER_PRESETS = [{"type": "sma", "period": 50}, {"type": "ema", "period": 26}]


@functools.lru_cache(maxsize=None)
def _signed_state(scenario, day):
    s = eng.new_state(scenario)
    for d in range(day):
        s = eng.advance(s, d)
    return s


def state_on(day, scenario="synthetic-b"):
    """A signed session advanced to simulated day `day` (0-based), with no orders; a fresh copy each call."""
    return copy.deepcopy(_signed_state(scenario, day))


def ask(client, state, symbol="SYN-TEC1", timeframe="daily", indicators=ALL_DAILY, **extra):
    body = {"state": state, "symbol": symbol, "timeframe": timeframe, "indicators": indicators} | extra
    return client.post("/api/analysis/indicators", json=body)


def data(resp):
    env = resp.get_json()
    assert resp.status_code == 200 and env["ok"], env
    return env["data"]


def error(resp, code="INVALID_REQUEST", status=400):
    env = resp.get_json()
    assert resp.status_code == status and env["ok"] is False and env["error"]["code"] == code, (resp.status_code, env)
    return env["error"]["message"]


def market():
    return paper_market.get("synthetic-b")


# ---- valid requests ----

def test_daily_request_returns_bars_and_every_requested_series_up_to_today(client):
    day = 60
    d = data(ask(client, state_on(day)))
    m = market()
    assert d["symbol"] == "SYN-TEC1" and d["timeframe"] == "daily" and d["date"] == m["dates"][day]
    assert d["final_day"] is False and "not a recommendation" in d["education"] and d["notice"] == m["notice"]
    assert len(d["bars"]) == day + 1 and d["bars"][-1]["time"] == m["dates"][day]
    assert d["bars"][0] == {"time": m["dates"][0], **m["bars"]["SYN-TEC1"][0]}  # integer cents, as /api/paper/market
    closes = [b["c"] for b in m["bars"]["SYN-TEC1"][:day + 1]]
    assert [(i["type"], i["period"]) for i in d["indicators"]] == [("sma", 20), ("ema", 12), ("rsi", 14),
                                                                   ("macd", [12, 26, 9])]
    for item in d["indicators"]:
        period = tuple(item["period"]) if isinstance(item["period"], list) else item["period"]
        assert item["series"] == ind.compute(item["type"], period, closes)
        assert all(len(values) == day + 1 for values in item["series"].values())


@pytest.mark.parametrize("presets", [ALL_DAILY, OTHER_PRESETS, []])
def test_every_offered_preset_and_an_empty_list_are_accepted(client, presets):
    d = data(ask(client, state_on(40), indicators=presets))
    assert len(d["indicators"]) == len(presets) and len(d["bars"]) == 41


def test_works_for_both_markets_and_every_symbol(client):
    for scenario, symbols in (("synthetic-a", ["SAMPLE-A", "SAMPLE-B"]), ("synthetic-b", list(market()["symbols"]))):
        for symbol in symbols:
            d = data(ask(client, state_on(30, scenario), symbol=symbol))
            assert d["symbol"] == symbol and len(d["bars"]) == 31


def test_request_never_changes_the_session(client):
    state = state_on(30)
    before = copy.deepcopy(state)
    d = data(ask(client, state))
    assert state == before and "state" not in d and "portfolio" not in d


# ---- not enough data ----

def test_insufficient_history_returns_nulls_not_estimates(client):
    d = data(ask(client, state_on(10)))  # 11 daily closes
    by = {i["type"]: i["series"] for i in d["indicators"]}
    assert by["sma"]["sma"] == [None] * 11 and by["rsi"]["rsi"] == [None] * 11
    assert by["ema"]["ema"][:11] == [None] * 11  # EMA 12 needs 12 closes
    assert all(v is None for series in by["macd"].values() for v in series)


def test_first_day_of_a_session(client):
    d = data(ask(client, state_on(0), timeframe="weekly"))
    assert len(d["bars"]) == 1 and d["bars"][0]["status"] == "partial"  # Thu 2 Jan, its week not finished yet
    assert all(v == [None] for i in d["indicators"] for v in i["series"].values())


# ---- no future data ----

@pytest.mark.parametrize("day", [0, 14, 33, 120, 248])
def test_values_never_depend_on_later_prices(client, day):
    m = market()
    full = [b["c"] for b in m["bars"]["SYN-TEC1"]]
    d = data(ask(client, state_on(day)))
    assert d["bars"][-1]["time"] == m["dates"][day] and len(d["bars"]) == day + 1
    for item in d["indicators"]:
        period = tuple(item["period"]) if isinstance(item["period"], list) else item["period"]
        whole = ind.compute(item["type"], period, full)  # computed with the whole scenario, then cut at today
        for name, values in item["series"].items():
            assert values == whole[name][:day + 1], (item["type"], name, day)


# ---- weekly: completed weeks only, Partial Week, Final Short Week ----

def day_of(iso):
    return market()["dates"].index(iso)


def test_weekly_partial_week_is_shown_but_never_calculated(client):
    d = data(ask(client, state_on(day_of("2025-08-14")), timeframe="weekly"))  # a Thursday
    weeks = d["bars"]
    assert weeks[-1]["status"] == "partial" and weeks[-1]["time"] == "2025-08-11" and weeks[-1]["end"] == "2025-08-14"
    assert all(w["status"] == "complete" for w in weeks[:-1]) and weeks[0]["days"] == 2
    completed_closes = [w["c"] for w in weeks[:-1]]
    for item in d["indicators"]:
        period = tuple(item["period"]) if isinstance(item["period"], list) else item["period"]
        expected = ind.compute(item["type"], period, completed_closes)
        for name, values in item["series"].items():
            assert len(values) == len(weeks) and values[-1] is None  # the Partial Week has no indicator value
            assert values[:-1] == expected[name]
    macd = next(i for i in d["indicators"] if i["type"] == "macd")["series"]
    assert macd["macd"][-2] is not None and macd["signal"][-2] is None  # 32 completed weeks: signal not enough data


def test_weekly_indicators_on_monday_to_thursday_equal_the_previous_friday(client):
    friday = data(ask(client, state_on(day_of("2025-08-08")), timeframe="weekly"))["indicators"]
    for iso in ("2025-08-11", "2025-08-12", "2025-08-13", "2025-08-14"):
        later = data(ask(client, state_on(day_of(iso)), timeframe="weekly"))["indicators"]
        for a, b in zip(friday, later):
            for name in a["series"]:
                assert b["series"][name][:-1] == a["series"][name], (iso, name)  # only the null partial entry added


def test_partial_week_turns_into_the_final_short_week_on_the_last_day(client):
    last = paper_market.last_day(market())
    before = data(ask(client, state_on(last - 1), timeframe="weekly"))
    final = data(ask(client, state_on(last), timeframe="weekly"))
    assert before["final_day"] is False and before["bars"][-1]["status"] == "partial"
    assert final["final_day"] is True and final["bars"][-1]["status"] == "final_short"
    assert final["bars"][-1]["time"] == "2025-12-15" and final["bars"][-1]["days"] == 3
    for a, b in zip(before["indicators"], final["indicators"]):
        for name in a["series"]:
            assert a["series"][name][-1] is None and b["series"][name][:-1] == a["series"][name][:-1]
    sma = final["indicators"][0]["series"]["sma"]
    assert sma[-1] is not None  # the Final Short Week is now part of the weekly calculation


def test_synthetic_a_ends_on_a_final_short_week_too(client):
    m = paper_market.get("synthetic-a")
    last = paper_market.last_day(m)
    d = data(ask(client, state_on(last, "synthetic-a"), symbol="SAMPLE-A", timeframe="weekly", indicators=[]))
    final = d["bars"][-1]
    expected = "complete" if date.fromisoformat(final["end"]).weekday() == 4 else "final_short"
    assert final["status"] == expected and final["end"] == m["dates"][last]


# ---- sessions: tampered, malformed, missing ----

def test_tampered_session_is_rejected(client):
    state = state_on(20)
    state["day"] = 200  # peek ahead without a valid signature
    error(ask(client, state), "INVALID_STATE")
    state = state_on(20)
    state["sig"] = "0" * len(state["sig"])
    error(ask(client, state), "INVALID_STATE")


@pytest.mark.parametrize("bad_state", [None, "", "x", 5, [], {}, {"sig": "a"}, {"schema": 1, "scenario": "synthetic-b"}])
def test_malformed_session_is_rejected(client, bad_state):
    error(ask(client, bad_state), "INVALID_STATE")


@pytest.mark.parametrize("raw", [b"", b"not json", b"[]", b"5", b'"text"', b"null", b"{"])
def test_body_must_be_a_json_object(client, raw):
    resp = client.post("/api/analysis/indicators", data=raw, content_type="application/json")
    error(resp)


def test_oversized_request_is_refused(client):
    error(ask(client, state_on(1), padding="x" * 70_000), "REQUEST_TOO_LARGE", 413)


def test_get_is_not_allowed(client):
    assert client.get("/api/analysis/indicators").status_code == 405


# ---- invalid symbols, timeframes, indicators and combinations ----

@pytest.mark.parametrize("symbol", ["AAPL", "SAMPLE-A", "syn-tec1", "", "../config", 7, None, ["SYN-TEC1"]])
def test_unknown_symbol(client, symbol):
    assert "symbol" in error(ask(client, state_on(5), symbol=symbol))


@pytest.mark.parametrize("timeframe", ["monthly", "Daily", "", None, 1, ["daily"]])
def test_unknown_timeframe(client, timeframe):
    assert "daily or weekly" in error(ask(client, state_on(5), timeframe=timeframe))


@pytest.mark.parametrize("item", [
    {"type": "bollinger", "period": 20}, {"type": "sma", "period": 21}, {"type": "sma", "period": 20.0},
    {"type": "sma", "period": "20"}, {"type": "sma", "period": True}, {"type": "rsi", "period": 9},
    {"type": "macd", "period": [12, 26, 8]}, {"type": "macd", "period": [12, 26]}, {"type": "macd", "period": 12},
    {"type": "macd", "period": [12.0, 26, 9]}, {"type": "macd", "period": [True, 26, 9]}, {"type": "sma"},
    {"type": "sma", "period": 20, "extra": 1}, {"period": 20}, "sma", None, 20, [],
])
def test_only_offered_presets_are_accepted(client, item):
    error(ask(client, state_on(5), indicators=[item]))


@pytest.mark.parametrize("indicators,phrase", [
    ([{"type": "sma", "period": 20}, {"type": "sma", "period": 50}, {"type": "ema", "period": 12}], "on the price"),
    ([{"type": "rsi", "period": 14}, {"type": "macd", "period": [12, 26, 9]}, {"type": "rsi", "period": 14}], "once"),
    ([{"type": "sma", "period": 20}, {"type": "sma", "period": 20}], "once"),
    ([{"type": "sma", "period": 20}] * 5, "up to four"),
    ("sma", "up to four"), ({"type": "sma", "period": 20}, "up to four"), (None, "up to four"),
])
def test_invalid_combinations(client, indicators, phrase):
    assert phrase in error(ask(client, state_on(5), indicators=indicators))


def test_pane_limit_is_enforced(client, monkeypatch):
    # the offered presets allow only two distinct panes; a hypothetical third preset must still be refused
    monkeypatch.setitem(ind.PRESETS, "rsi", (14, 21))
    three = [{"type": "rsi", "period": 14}, {"type": "rsi", "period": 21}, {"type": "macd", "period": [12, 26, 9]}]
    assert "panes" in error(ask(client, state_on(5), indicators=three))


def test_garbage_never_causes_a_server_error(client):
    state = state_on(5)
    bodies = [
        {}, {"state": state}, {"state": state, "symbol": "SYN-TEC1"}, {"state": state, "symbol": {}, "timeframe": {},
                                                                       "indicators": {}},
        {"state": state, "symbol": "SYN-TEC1", "timeframe": "daily", "indicators": [{"type": {}, "period": {}}]},
        {"state": state, "symbol": "SYN-TEC1", "timeframe": "daily", "indicators": [{"type": [], "period": []}]},
        {"state": [state], "symbol": "SYN-TEC1", "timeframe": "weekly", "indicators": []},
        {"state": state | {"orders": "x"}, "symbol": "SYN-TEC1", "timeframe": "daily", "indicators": []},
    ]
    for body in bodies:
        resp = client.post("/api/analysis/indicators", json=body)
        env = resp.get_json()
        assert resp.status_code == 400 and env["ok"] is False and env["error"]["code"] in ("INVALID_REQUEST",
                                                                                          "INVALID_STATE"), body


# ---- separation from trading ----

def test_analysis_never_touches_the_trading_engine_writes(monkeypatch, client):
    state = state_on(15)
    for name in ("confirm", "cancel", "advance", "new_state", "_sign"):
        monkeypatch.setattr(eng, name, lambda *a, **k: pytest.fail("analysis must not change a session"))
    data(ask(client, state))


def test_seeded_fuzz_of_malformed_requests_never_returns_500(client):
    import random
    rng = random.Random(20261027)
    state = state_on(8)
    atoms = [None, True, 0, -1, 20, 20.5, "", "sma", "daily", "weekly", "SYN-TEC1", [], {}, [12, 26, 9], "x" * 50]

    def junk(depth=0):
        if depth > 2 or rng.random() < 0.5:
            return rng.choice(atoms)
        if rng.random() < 0.5:
            return [junk(depth + 1) for _ in range(rng.randint(0, 4))]
        keys = rng.sample(["type", "period", "state", "symbol", "timeframe", "indicators", "extra"], rng.randint(0, 3))
        return {k: junk(depth + 1) for k in keys}

    for _ in range(400):
        body = {"state": rng.choice([state, junk()]), "symbol": rng.choice(["SYN-TEC1", junk()]),
                "timeframe": rng.choice(["daily", "weekly", junk()]),
                "indicators": rng.choice([ALL_DAILY, [junk() for _ in range(rng.randint(0, 5))], junk()])}
        resp = client.post("/api/analysis/indicators", json=body)
        assert resp.status_code in (200, 400), (resp.status_code, body)
        assert resp.get_json()["ok"] is (resp.status_code == 200)
