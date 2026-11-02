"""P5 step 8: the strategy guide (data/strategy_guide.json) against the owner-approved docs/P5_CONTENT.md, its
validation, the card readings against the API's own numbers, GET /api/backtest/guide, and what a damaged guide does."""
import copy
import json
import os
import re

import pytest

from services import backtest as bt
from services import paper_market
from services import strategy_guide as sg
from tests.test_backtest_api import ask, data, error, state_on

ROOT = os.path.join(os.path.dirname(__file__), "..")
G = sg.load()
M = paper_market.get("synthetic-b")


def approved():
    with open(os.path.join(ROOT, "docs", "P5_CONTENT.md"), encoding="utf-8") as f:
        return re.sub(r"\s+", " ", f.read())


def texts(node=G, path=""):
    """Every string in the guide with its path, except the provenance note."""
    if isinstance(node, dict):
        return [t for k, v in node.items() if k != "source" for t in texts(v, f"{path}.{k}".strip("."))]
    return [(path, node)]


def reply(symbol, day, preset, costs):
    """An /api/backtest/run-shaped reply built from the engine for the same session days."""
    r = bt.run(M["dates"][:day + 1], M["bars"][symbol][:day + 1], preset, costs)["result"]
    return {"symbol": symbol, "preset": preset, "costs": costs, "result": {
        "strategy": r["strategy"], "benchmark": r["benchmark"], "difference_pp": r["difference_pp"],
        "unacted_signal": r["strategy"]["unacted_signal"]}}


# ---- the approved text, word for word ----

@pytest.mark.parametrize("path, text", texts())
def test_every_guide_sentence_is_in_the_approved_content_word_for_word(path, text):
    assert text in approved(), path


def test_the_guide_validates_and_covers_every_card():
    assert set(G["rules"]) == set(bt.RULES) and set(G["metrics"]) == set(sg.METRIC_PARTS)
    assert G["label"] == "Our plain summary" and "not a recommendation to buy or sell" in G["footer"]
    assert all(t.strip() for _, t in texts())


def test_the_guide_never_uses_advice_prediction_or_validation_words():
    for path, text in texts():
        low = text.lower()
        for phrase in ("you should", "buy now", "sell now", "buy signal", "sell signal", "guaranteed", "sure thing",
                       "predict", "expect", "outperform", "beat the market", "best", "winning", "recommend",
                       "in-sample", "out-of-sample", "bullish", "bearish"):
            if phrase == "recommend" and path == "footer":
                continue  # "not a recommendation"
            assert not re.search(r"\b" + re.escape(phrase), low), (path, phrase)
        assert not re.search(r"\bwill\b", low), path


@pytest.mark.parametrize("damage", [
    lambda g: g.pop("footer"), lambda g: g["rules"]["sma_cross"].pop("watch"),
    lambda g: g["metrics"]["drawdown"]["readings"].update(cash=""), lambda g: g["halves"].update(how=5),
    lambda g: g.update(rules=[]), lambda g: g["buy_hold"]["readings"].pop("skipped")])
def test_a_guide_missing_any_text_is_refused(tmp_path, damage):
    broken = copy.deepcopy(G)
    damage(broken)
    path = tmp_path / "guide.json"
    path.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        sg.load(str(path))


# ---- readings: the API's own numbers, formatted ----

def test_the_mockup_run_reads_exactly():
    got = sg.readings(reply("SYN-HLT1", 160, "sma_cross", "example"))
    assert got == {
        "rule": "The rule acted on 3 crossings: 2 up through the 50-day average and 1 back down.",
        "buy_hold": "Buy and hold bought 99 shares at the Day 51 open ($100.83, fill price $100.94) and kept them.",
        "total_return": "The $10,000 became $10,442.81, a change of +4.43%.",
        "difference": "This rule ended at $10,442.81 (+4.43%). Buying and holding SYN-HLT1 over the same days ended at "
                      "$11,029.60 (+10.30%), so the rule ended 5.87 points lower.",
        "drawdown": "The value fell 10.51% from its high on May 12 to a low on Jun 9.",
        "volatility": "The value's daily changes had a standard deviation of 0.96%.",
        "trades": "The rule bought 2 times and sold once.",
        "days_invested": "Shares were held at the close on 49 of 111 test days (44.14%).",
        "costs": "The example costs added up to $30.91 across 3 fills.",
    }


def test_no_trades_reads_as_the_corrected_content_says():
    got = sg.readings(reply("SYN-TEC1", 160, "sma_cross", "example"))
    assert got["rule"] == ("The 20-day average never crossed above the 50-day average while the rule was in cash, so it "
                           "never bought.")
    assert got["drawdown"] == "The value stayed at $10,000.00 in cash, so it never dropped."
    assert got["trades"] == "The rule bought 0 times and sold 0 times."
    assert got["difference"].endswith("so the rule ended 12.98 points lower.")


def test_a_last_day_signal_counts_as_a_crossing_the_rule_acted_on():
    got = sg.readings(reply("SYN-CON1", 164, "sma_cross", "example"))
    assert got["rule"] == "The rule acted on 4 crossings: 2 up through the 50-day average and 2 back down."


def test_the_rsi_rule_and_no_costs():
    got = sg.readings(reply("SYN-ENR1", 160, "rsi_threshold", "none"))
    assert got["rule"] == "The rule acted on 2 RSI readings: 1 below 30 while in cash and 1 above 70 while holding."
    assert got["costs"] == "No costs were charged." and got["trades"] == "The rule bought once and sold once."


def hand_made(values, fills=(), skipped=(), unacted=None, bh_skip=False, preset="sma_cross", diff=0.0):
    """A reply with chosen numbers, for the cases no synthetic ticker reaches."""
    days = len(values) - 1
    metrics = {"final_value_cents": values[-1], "total_return_pct": round((values[-1] - 1e6) / 1e4, 2),
               "max_drawdown": None, "max_drawdown_pct": 0.0, "daily_volatility_pct": 0.5, "buys": 0, "sells": 0,
               "evaluation_days": days, "days_invested": 0, "days_invested_pct": 0.0, "costs_paid_cents": 0}
    bench = {"metrics": dict(metrics), "fills": [] if bh_skip else [{"shares": 10, "open_cents": 100, "price_cents": 101}],
             "skipped": [{"price_cents": 2_002_000}] if bh_skip else []}
    return {"symbol": "SYN-X", "preset": preset, "costs": "example", "result": {
        "strategy": {"metrics": metrics, "fills": list(fills), "skipped": list(skipped)}, "benchmark": bench,
        "difference_pp": diff, "unacted_signal": unacted}}


def test_singular_forms_skipped_entries_and_a_level_result():
    one = sg.readings(hand_made([1_000_000] * 30, fills=[{"side": "buy"}]))
    assert one["rule"] == "The rule acted on 1 crossing: 1 up through the 50-day average and 0 back down."
    assert one["costs"] == "The example costs added up to $0.00 across 1 fill."
    rsi = sg.readings(hand_made([1_000_000] * 30, skipped=[{}], preset="rsi_threshold"))
    assert rsi["rule"] == "The rule acted on 1 RSI reading: 1 below 30 while in cash and 0 above 70 while holding."
    skip = sg.readings(hand_made([1_000_000] * 30, bh_skip=True))
    assert skip["buy_hold"] == ("Buy and hold could not afford one share at the Day 51 open (fill price $20,020.00), so "
                                "it stayed in cash.")
    assert skip["difference"].endswith("over the same days ended at $10,000.00 (0.00%), so the rule ended level with "
                                       "buying and holding (0.00 points).")
    single = hand_made([1_000_000] * 30)
    single["result"]["benchmark"]["fills"][0]["shares"] = 1
    assert sg.readings(single)["buy_hold"].startswith("Buy and hold bought 1 share at the Day 51 open")
    held = hand_made([1_000_000, 1_000_100, 1_000_200])
    held["result"]["strategy"]["metrics"]["days_invested"] = 2
    assert sg.readings(held)["drawdown"] == "The value never fell below an earlier high on these days."
    down = sg.readings(hand_made([1_000_000] * 30, diff=-1.5, unacted={"side": "sell"}))
    assert down["rule"] == "The rule acted on 1 crossing: 0 up through the 50-day average and 1 back down."


@pytest.mark.parametrize("preset", bt.RULES)
@pytest.mark.parametrize("costs", ["example", "none"])
def test_every_reading_for_every_symbol_is_filled_and_states_the_apis_numbers(preset, costs):
    for market in (paper_market.get("synthetic-a"), M):
        for symbol in market["symbols"]:
            day = len(market["dates"]) - 1
            r = bt.run(market["dates"], market["bars"][symbol], preset, costs)["result"]
            got = sg.readings({"symbol": symbol, "preset": preset, "costs": costs, "result": {
                "strategy": r["strategy"], "benchmark": r["benchmark"], "difference_pp": r["difference_pp"],
                "unacted_signal": r["strategy"]["unacted_signal"]}})
            sm = r["strategy"]["metrics"]
            assert all("{" not in v and "}" not in v and v.endswith(".") for v in got.values()), (symbol, got)
            assert f"{abs(sm['total_return_pct']):.2f}%" in got["total_return"]
            assert f"{sm['daily_volatility_pct']:.2f}%" in got["volatility"]
            assert f"on {sm['days_invested']} of {sm['evaluation_days']} test days" in got["days_invested"], day


# ---- the endpoints ----

def test_the_guide_endpoint_serves_the_file(client):
    resp = client.get("/api/backtest/guide")
    env = resp.get_json()
    assert resp.status_code == 200 and env["ok"] and env["source"] is None and env["data"] == G
    assert client.post("/api/backtest/guide").status_code == 405


def test_the_run_reply_carries_the_readings(client):
    d = data(ask(client, state_on(160)))
    assert d["result"]["readings"] == sg.readings(d)
    assert d["result"]["readings"]["rule"].startswith("The rule acted on 3 crossings")
    assert data(ask(client, state_on(40)))["result"] is None  # not enough data: no cards to read


def test_a_damaged_guide_costs_the_explanations_never_the_results(client, monkeypatch, tmp_path):
    path = tmp_path / "guide.json"
    path.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(sg, "GUIDE_PATH", str(path))
    monkeypatch.setattr(sg, "_guide", None)
    monkeypatch.setattr(sg.load, "__defaults__", (str(path),))
    assert error(client.get("/api/backtest/guide"), "INTERNAL_ERROR", 500) == "Something went wrong. Please try again."
    d = data(ask(client, state_on(160)))
    assert d["result"]["readings"] is None and d["result"]["strategy"]["metrics"]["total_return_pct"] == 4.43
