"""Paper Trading Lab engine: next-open fills, cash and share checks, cost basis and P/L in integer cents, duplicate
and repeated requests, tampered state, look-ahead and the end of a scenario. Small hand-built markets keep the
arithmetic checkable by hand."""
import copy
import json

import pytest

import config
from services import paper_engine as eng
from services import paper_market
from services.errors import InvalidRequest, InvalidState

START = 1_000_000


def bars(*rows):
    return [{"o": o, "h": max(o, c), "l": min(o, c), "c": c, "v": 1000} for o, c in rows]


@pytest.fixture
def market(monkeypatch):
    """Registers a tiny test scenario. Call it with {symbol: [(open, close), ...]}."""
    def install(series):
        days = len(next(iter(series.values())))
        m = {"id": "test-m", "label": "Test market", "kind": "synthetic", "notice": "Test prices.", "timeframe": "1D",
             "symbols": {s: {"name": f"{s} (fictional)"} for s in series},
             "dates": [f"2025-01-{d + 1:02d}" for d in range(days)],
             "bars": {s: bars(*rows) for s, rows in series.items()}}
        monkeypatch.setitem(paper_market._scenarios, "test-m", m)
        monkeypatch.setattr(paper_market, "scenario_ids", lambda: ["synthetic-a", "test-m"])
        return eng.new_state("test-m")
    return install


def order(oid, side, shares, symbol="AAA"):
    return {"id": oid, "symbol": symbol, "side": side, "shares": shares}


def place(state, *orders):
    for o in orders:
        state, duplicate = eng.confirm(state, o)
        assert duplicate is False
    return state


def step(state):
    return eng.advance(state, eng.verify(state)[0]["day"])


def summary(state):
    body, m = eng.verify(state)
    return eng.portfolio(body, m)


def orders_by_id(state):
    return {o["id"]: o for o in eng.verify(state)[0]["orders"]}


# ---- starting point and labels ----

def test_new_session_starts_with_ten_thousand_fictional_dollars():
    view = eng.view(eng.new_state("synthetic-a"))
    p = view["portfolio"]
    assert p["cash_cents"] == p["portfolio_value_cents"] == START and p["positions"] == [] and p["total_pl_cents"] == 0
    assert view["day"] == {"index": 0, "date": "2025-01-02", "is_last": False, "ended": False}
    notices = " ".join(view["notices"])
    assert "No real securities are bought or sold." in notices
    for cost in ("commissions and fees", "bid-ask spread", "slippage", "market impact"):
        assert cost in notices


# ---- execution ----

def test_orders_fill_at_the_next_days_open_not_todays_close(market):
    s = market({"AAA": [(1000, 1050), (1100, 1200), (1300, 1250)]})
    s = place(s, order("order-0001", "buy", 10))
    assert orders_by_id(s)["order-0001"]["status"] == "pending" and summary(s)["cash_cents"] == START
    s = step(s)
    o = orders_by_id(s)["order-0001"]
    assert o["status"] == "filled" and o["fill_day"] == 1
    p = summary(s)
    assert p["transactions"][0]["price_cents"] == 1100  # day 1 open, not day 0 close (1050)
    assert p["cash_cents"] == START - 11_000
    assert p["positions"][0]["unrealized_pl_cents"] == 10 * 1200 - 11_000  # valued at day 1 close


def test_insufficient_buying_power_counts_pending_buys(market):
    s = market({"AAA": [(1000, 1000), (1000, 1000)]})
    with pytest.raises(InvalidRequest, match="Not enough fictional cash"):
        eng.confirm(s, order("order-0001", "buy", 1001))  # $10,010 estimate > $10,000
    s = place(s, order("order-0001", "buy", 600))
    preview = eng.preview(s, order("x", "buy", 401))
    assert preview["ok"] is False and preview["problems"][0]["code"] == "insufficient_cash"
    assert eng.preview(s, order("x", "buy", 400))["ok"] is True


def test_gap_up_at_the_open_rejects_a_buy_with_a_reason(market):
    s = market({"AAA": [(10_000, 10_000), (20_000, 20_000)]})
    s = place(s, order("order-0001", "buy", 99))  # $9,900 at today's close: allowed
    s = step(s)
    o = orders_by_id(s)["order-0001"]
    assert o["status"] == "rejected" and "opening price of $200.00" in o["reason"] and "needed $19,800.00" in o["reason"]
    assert summary(s)["cash_cents"] == START and summary(s)["positions"] == []


def test_partial_and_full_sales_with_average_cost_rounding(market):
    s = market({"AAA": [(1000, 1000), (1001, 1001), (1002, 1002), (1100, 1100), (900, 900)]})
    s = step(place(s, order("buy-00001", "buy", 3)))          # 3 @ $10.01 -> basis 3003
    s = step(place(s, order("buy-00002", "buy", 4)))          # 4 @ $10.02 -> basis 7011, 7 shares
    pos = summary(s)["positions"][0]
    assert (pos["shares"], pos["cost_basis_cents"], pos["average_cost_cents"]) == (7, 7011, 1002)  # 1001.57 -> 1002
    s = step(place(s, order("sell-0001", "sell", 3)))         # 3 @ $11.00; basis share 7011*3//7 = 3004
    p = summary(s)
    assert p["transactions"][-1]["realized_pl_cents"] == 3300 - 3004
    assert (p["positions"][0]["shares"], p["positions"][0]["cost_basis_cents"]) == (4, 4007)
    s = step(place(s, order("sell-0002", "sell", 4)))         # sell all @ $9.00: whole remaining basis
    p = summary(s)
    assert p["transactions"][-1]["realized_pl_cents"] == 3600 - 4007
    assert p["positions"] == [] and p["realized_pl_cents"] == 296 - 407
    assert p["cash_cents"] == START - 3003 - 4008 + 3300 + 3600 == START + p["realized_pl_cents"]


def test_unrealized_and_total_pl_use_the_current_close(market):
    s = market({"AAA": [(1000, 1000), (1000, 1234)], "BBB": [(500, 500), (500, 450)]})
    s = step(place(s, order("buy-00001", "buy", 10), order("buy-00002", "buy", 20, "BBB")))
    p = summary(s)
    by = {x["symbol"]: x for x in p["positions"]}
    assert by["AAA"]["unrealized_pl_cents"] == 2340 and by["BBB"]["unrealized_pl_cents"] == -1000
    assert p["unrealized_pl_cents"] == 1340 and p["total_pl_cents"] == 1340
    assert p["portfolio_value_cents"] == p["cash_cents"] + 12_340 + 9000


def test_selling_more_than_held_counts_pending_sells(market):
    s = market({"AAA": [(1000, 1000), (1000, 1000), (1000, 1000)]})
    s = step(place(s, order("buy-00001", "buy", 5)))
    with pytest.raises(InvalidRequest, match="at most 5 shares"):
        eng.confirm(s, order("sell-0001", "sell", 6))
    s = place(s, order("sell-0001", "sell", 3))
    assert eng.preview(s, order("x", "sell", 3))["problems"][0]["code"] == "insufficient_shares"
    assert eng.preview(s, order("x", "sell", 2, "AAA"))["ok"] is True


@pytest.mark.parametrize("bad, code", [
    ({"shares": 0}, "invalid_quantity"), ({"shares": -1}, "invalid_quantity"), ({"shares": 1.5}, "invalid_quantity"),
    ({"shares": True}, "invalid_quantity"), ({"shares": "10"}, "invalid_quantity"), ({"shares": 100_001}, "invalid_quantity"),
    ({"symbol": "AAPL"}, "unsupported_symbol"), ({"side": "short"}, "invalid_side"),
])
def test_invalid_orders_are_rejected_with_a_reason(market, bad, code):
    s = market({"AAA": [(1000, 1000), (1000, 1000)]})
    result = eng.preview(s, {**order("x", "buy", 1), **bad})
    assert result["ok"] is False and code in {p["code"] for p in result["problems"]}
    with pytest.raises(InvalidRequest):
        eng.confirm(s, {**order("order-0001", "buy", 1), **bad})


def test_cancel_records_a_reason_and_cannot_undo_a_fill(market):
    s = market({"AAA": [(1000, 1000), (1000, 1000), (1000, 1000)]})
    s = place(s, order("order-0001", "buy", 1), order("order-0002", "buy", 1))
    s = eng.cancel(s, "order-0001")
    assert orders_by_id(s)["order-0001"]["reason"] == "Cancelled by you before it filled."
    assert eng.cancel(s, "order-0001") == s  # cancelling twice changes nothing
    s = step(s)
    with pytest.raises(InvalidRequest, match="already filled"):
        eng.cancel(s, "order-0002")
    with pytest.raises(InvalidRequest):
        eng.cancel(s, "no-such-order")


# ---- duplicates and repeats ----

def test_duplicate_order_ids_are_not_processed_twice(market):
    s = market({"AAA": [(1000, 1000), (1000, 1000), (1000, 1000)]})
    s = place(s, order("order-0001", "buy", 10))
    again, duplicate = eng.confirm(s, order("order-0001", "buy", 10))
    assert duplicate is True and again == s and len(orders_by_id(s)) == 1
    s = step(s)
    again, duplicate = eng.confirm(s, order("order-0001", "buy", 10))  # after the fill, too
    assert duplicate is True and len(summary(again)["transactions"]) == 1


@pytest.mark.parametrize("oid", ["short", "has space1", "x" * 65, 12345678, None])
def test_order_ids_must_be_well_formed(market, oid):
    s = market({"AAA": [(1000, 1000), (1000, 1000)]})
    with pytest.raises(InvalidRequest, match="unique id"):
        eng.confirm(s, {**order("ignored1", "buy", 1), "id": oid})


def test_advancing_is_deterministic_and_refuses_a_stale_day(market):
    s = market({"AAA": [(1000, 1000), (1100, 1100), (1200, 1200)]})
    s = place(s, order("order-0001", "buy", 10))
    first, second = eng.advance(s, 0), eng.advance(s, 0)
    assert first == second  # same input, same result
    with pytest.raises(InvalidRequest, match="already moved past"):
        eng.advance(first, 0)  # the same click sent again after the session moved on
    assert len(summary(first)["transactions"]) == 1


# ---- tampered or invalid state ----

def tamper(state, change):
    bad = copy.deepcopy(state)
    change(bad)
    return bad


@pytest.mark.parametrize("change", [
    lambda s: s.update(day=s["day"] + 1),
    lambda s: s["orders"][0].update(shares=1),
    lambda s: s["orders"][0].update(status="filled", fill_day=1),
    lambda s: s.update(cash_cents=99_999_999),
    lambda s: s.update(sig="0" * 64),
    lambda s: s.pop("sig"),
    lambda s: s.update(scenario="synthetic-a"),
    lambda s: s["orders"].append(copy.deepcopy(s["orders"][0])),
])
def test_tampered_state_is_rejected(market, change):
    s = place(market({"AAA": [(1000, 1000), (1000, 1000)]}), order("order-0001", "buy", 10))
    with pytest.raises(InvalidState):
        eng.view(tamper(s, change))


@pytest.mark.parametrize("state", [None, [], "state", {"schema": 1}])
def test_malformed_state_is_rejected(state):
    with pytest.raises(InvalidState):
        eng.view(state)


@pytest.mark.parametrize("change", [
    lambda b: b.update(schema=2),
    lambda b: b.update(day=999),
    lambda b: b["orders"].append({"id": "order-0001", "symbol": "AAA", "side": "sell", "shares": 1, "placed_day": 0,
                                  "status": "filled", "reason": None, "fill_day": 0}),
])
def test_signed_but_impossible_state_is_still_rejected(market, change):
    s = market({"AAA": [(1000, 1000), (1000, 1000)]})
    body = {k: v for k, v in s.items() if k != "sig"}
    change(body)
    with pytest.raises(InvalidState):
        eng.view(eng._sign(body))


def test_a_local_key_is_created_once_when_no_secret_is_configured(monkeypatch, tmp_path):
    key = tmp_path / "paper_state.key"
    monkeypatch.setattr(config, "PAPER_STATE_SECRET", "")
    monkeypatch.setattr(config, "PAPER_KEY_PATH", str(key))
    s = eng.new_state("synthetic-a")
    first = key.read_text()
    assert len(first) == 64 and eng.view(s)["day"]["index"] == 0
    eng.new_state("synthetic-a")
    assert key.read_text() == first  # never overwritten


# ---- look-ahead and the end of a scenario ----

def test_no_bars_beyond_the_current_day_are_revealed():
    s = eng.new_state("synthetic-a")
    for _ in range(5):
        s = step(s)
    data = eng.market_bars(s)
    m = paper_market.get("synthetic-a")
    assert data["dates"] == m["dates"][:6]
    assert all(len(b) == 6 for b in data["bars"].values())
    view = eng.view(s)
    assert view["quotes"]["SAMPLE-A"]["close_cents"] == m["bars"]["SAMPLE-A"][5]["c"]
    assert eng.preview(s, order("x", "buy", 1, "SAMPLE-A"))["reference_close_cents"] == m["bars"]["SAMPLE-A"][5]["c"]


def test_pending_orders_are_cancelled_when_the_scenario_ends(market):
    s = market({"AAA": [(1000, 1000), (1000, 1000), (1000, 1000)]})
    s = step(step(s))  # day 2 is the last day
    assert "last simulated day" in eng.preview(s, order("x", "buy", 1))["warning"]
    s = place(s, order("order-0001", "buy", 1))
    s = step(s)
    o = orders_by_id(s)["order-0001"]
    assert o["status"] == "cancelled" and "scenario ended" in o["reason"]
    assert eng.view(s)["day"]["ended"] is True and summary(s)["cash_cents"] == START
    with pytest.raises(InvalidRequest, match="has ended"):
        eng.confirm(s, order("order-0002", "buy", 1))
    with pytest.raises(InvalidRequest, match="has ended"):
        eng.advance(s, 2)


# ---- routes ----

def post(client, path, body):
    return client.post(f"/api/paper/{path}", json=body)


def test_full_round_trip_through_the_api(client):
    scen = client.get("/api/paper/scenarios").get_json()["data"]
    assert scen["scenarios"][0]["id"] == "synthetic-a" and "No real securities" in scen["notices"][0]
    view = post(client, "new", {"scenario": "synthetic-a"}).get_json()["data"]
    state = view["state"]
    prev = post(client, "preview", {"state": state, "order": {"symbol": "SAMPLE-A", "side": "buy", "shares": 5}}).get_json()["data"]
    assert prev["ok"] is True and "next simulated day's opening price" in prev["fill_note"]
    conf = post(client, "confirm", {"state": state, "order": {"id": "order-0001", "symbol": "SAMPLE-A", "side": "buy",
                                                              "shares": 5}}).get_json()["data"]
    assert conf["duplicate"] is False and conf["orders"][0]["status"] == "pending"
    adv = post(client, "advance", {"state": conf["state"], "expected_day": 0}).get_json()["data"]
    assert adv["day"]["index"] == 1 and adv["orders"][0]["status"] == "filled"
    bars = post(client, "market", {"state": adv["state"]}).get_json()["data"]
    assert len(bars["dates"]) == 2 and "Not real market data" in bars["notice"]
    stale = post(client, "advance", {"state": conf["state"], "expected_day": 1})
    assert stale.status_code == 400


def test_api_rejects_bad_input(client):
    assert post(client, "view", {"state": {"day": 0}}).get_json()["error"]["code"] == "INVALID_STATE"
    assert post(client, "new", {"scenario": "real-nasdaq"}).status_code == 400
    assert client.post("/api/paper/view", data="not json", content_type="application/json").status_code == 400
    big = client.post("/api/paper/view", data="x" * (70 * 1024), content_type="application/json")
    assert big.status_code == 413 and big.get_json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_actions_never_change_the_callers_state(market):
    s = market({"AAA": [(1000, 1000), (1000, 1000)]})
    before = copy.deepcopy(s)
    s2 = place(s, order("order-0001", "buy", 1))
    snapshot = copy.deepcopy(s2)
    eng.advance(s2, 0)
    eng.cancel(s2, "order-0001")
    assert s == before and s2 == snapshot


def test_a_full_order_log_fits_within_the_request_size_limit():
    filler = [{"id": f"order-{i:059d}", "symbol": "SAMPLE-A", "side": "buy", "shares": eng.MAX_SHARES, "placed_day": 0,
               "status": "rejected", "reason": "Not enough fictional cash at the opening price of $1,234.56: needed "
               "$123,456,000.00, had $10,000.00.", "fill_day": None} for i in range(eng.MAX_ORDERS)]
    state = eng._sign({"schema": 1, "scenario": "synthetic-a", "day": 119, "ended": False, "orders": filler})
    request_body = {"state": state, "order": {"id": "x" * 64, "symbol": "SAMPLE-A", "side": "buy", "shares": 1}}
    assert len(json.dumps(request_body)) < config.MAX_REQUEST_BYTES


# ---- signing key: strength, persistence across restarts, concurrency, round trips ----

def use_key_file(monkeypatch, path):
    monkeypatch.setattr(config, "PAPER_STATE_SECRET", "")
    monkeypatch.setattr(config, "PAPER_KEY_PATH", str(path))


def test_a_short_configured_secret_is_refused(monkeypatch):
    monkeypatch.setattr(config, "PAPER_STATE_SECRET", "too-short")
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        eng.new_state("synthetic-a")


@pytest.mark.parametrize("content", ["", "abc", "z" * 64, "0" * 63])
def test_a_damaged_key_file_is_never_used_to_sign(monkeypatch, tmp_path, content):
    key = tmp_path / "paper_state.key"
    key.write_text(content)
    use_key_file(monkeypatch, key)
    with pytest.raises(RuntimeError, match="damaged"):
        eng.new_state("synthetic-a")


def test_sessions_survive_a_server_restart_with_the_same_key_file(monkeypatch, tmp_path):
    key = tmp_path / "paper_state.key"
    use_key_file(monkeypatch, key)
    s = eng.advance(eng.new_state("synthetic-a"), 0)
    monkeypatch.setattr(eng, "_keys", {})  # a restarted process starts with no cached key
    assert eng.view(s)["day"]["index"] == 1
    key.unlink()  # a deleted key file means a new key, so old sessions can no longer be verified
    monkeypatch.setattr(eng, "_keys", {})
    with pytest.raises(InvalidState):
        eng.view(s)


def test_changing_the_configured_secret_ends_existing_sessions(monkeypatch):
    s = eng.new_state("synthetic-a")
    monkeypatch.setattr(config, "PAPER_STATE_SECRET", "a-different-secret-that-is-long-enough-1234")
    with pytest.raises(InvalidState):
        eng.view(s)


def test_concurrent_first_requests_agree_on_one_key(monkeypatch, tmp_path):
    import threading
    key = tmp_path / "paper_state.key"
    use_key_file(monkeypatch, key)
    states, threads = [], [threading.Thread(target=lambda: states.append(eng.new_state("synthetic-a"))) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(states) == 16 and all(eng.view(s)["day"]["index"] == 0 for s in states)
    assert len(key.read_text()) == 64 and not list(tmp_path.glob("*.tmp"))


def test_state_survives_a_json_round_trip_through_the_browser(market):
    s = market({"AAA": [(1000, 1000), (1100, 1100), (1200, 1200)]})
    s = step(place(s, order("order-0001", "buy", 3)))
    s = place(s, order("order-0002", "sell", 1))
    browser_copy = json.loads(json.dumps(s, indent=2))  # key order and spacing may change in transit
    assert eng.view(browser_copy)["portfolio"] == eng.view(s)["portfolio"]
    assert step(browser_copy) == step(s)


def test_replaying_the_log_from_scratch_matches_the_live_session(market):
    s = market({"AAA": [(1000, 1010), (1020, 990), (980, 1000), (1050, 1060), (1040, 1040)]})
    s = step(place(s, order("order-0001", "buy", 7)))
    s = step(place(s, order("order-0002", "buy", 5), order("order-0003", "sell", 4)))
    s = step(place(s, order("order-0004", "sell", 8)))
    p = summary(s)  # recomputed purely from the signed log and the market
    cash = START - 7 * 1020 - 5 * 980 + 4 * 980 + 8 * 1050
    assert p["cash_cents"] == cash and p["positions"] == []
    assert p["realized_pl_cents"] == cash - START
