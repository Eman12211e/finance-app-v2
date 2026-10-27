"""Educational explanations (P4 step 6): every reading branch from unrounded values, rounding that never contradicts
the chosen sentence, Not enough data / Partial Week / Final Short Week, the approved text kept word for word, no
advice or prediction wording, and the analysis API carrying the same sentences."""
import json
import os
import re

import pytest

from services import explain
from services import indicators as ind

ROOT = os.path.join(os.path.dirname(__file__), "..")
G = explain.guide()
SHARED = G["shared"]
PARTIAL = SHARED["partial_week"]


def bars(*closes):
    return [{"time": f"2025-01-{i + 1:02d}", "c": c} for i, c in enumerate(closes)]


def read(kind, period, values, closes, timeframe="daily", **kw):
    return explain.reading(kind, period, values, bars(*closes), timeframe, **kw)


# ---- SMA and EMA: the close against the unrounded average ----

@pytest.mark.parametrize("kind,period,label", [("sma", 20, "average"), ("sma", 50, "average"), ("ema", 12, "EMA"),
                                               ("ema", 26, "EMA")])
def test_average_above_below_equal(kind, period, label):
    assert read(kind, period, {kind: [18999.1]}, [19996]) == (
        f"The latest close, $199.96, is above its {period}-day {label} of $189.99.")
    assert read(kind, period, {kind: [20000.4]}, [19996]) == (
        f"The latest close, $199.96, is below its {period}-day {label} of $200.00.")
    assert read(kind, period, {kind: [19996.0]}, [19996]) == f"The latest close, $199.96, is at its {period}-day {label}."


def test_average_a_fraction_of_a_cent_away_shows_enough_decimals():
    # 199.958 rounds to 199.96, which would read "above its average of $199.96"; the unrounded value decides and the
    # shown number keeps the decimals that make the sentence true
    assert read("sma", 20, {"sma": [19995.8]}, [19996]) == (
        "The latest close, $199.96, is above its 20-day average of $199.958.")
    assert read("ema", 12, {"ema": [19996.004]}, [19996]) == (
        "The latest close, $199.96, is below its 12-day EMA of $199.96004.")


# ---- RSI: thresholds on unrounded values, with truthful rounding ----

@pytest.mark.parametrize("value,zone,shown", [
    (70.0, "high", "70.0"), (77.89, "high", "77.9"), (69.996, "upper", "69.996"), (69.94, "upper", "69.9"),
    (30.0, "low", "30.0"), (12.3, "low", "12.3"), (30.004, "lower", "30.004"), (30.06, "lower", "30.1"),
    (50.0, "middle", "50.0"), (50.04, "upper", "50.04"), (49.96, "lower", "49.96"), (56.09, "upper", "56.1"),
    (49.0, "lower", "49.0"), (70.04, "high", "70.0"), (29.96, "low", "30.0"),
])
def test_rsi_zone_comes_from_the_unrounded_value(value, zone, shown):
    assert read("rsi", 14, {"rsi": [value]}, [100]) == G["indicators"]["rsi"]["readings"][zone].format(value=shown)


# ---- MACD: side of zero, signal line and change, all unrounded ----

def macd(line, signal, hist, prev=None):
    return {"macd": [None, line], "signal": [None, signal], "histogram": [prev, hist]}


def test_macd_worked_example_from_day_161():
    assert read("macd", (12, 26, 9), macd(-374.72, -580.58, 205.86, 114.72), [1, 2]) == (
        "The MACD line is -3.75: below zero, so the 12-day EMA is below the 26-day EMA. It is above its signal line "
        "(-5.81). The gap between them widened since the previous day.")


@pytest.mark.parametrize("hist,prev,change", [
    (2.0, 1.0, "widened"), (-2.0, -1.0, "widened"), (1.0, 2.0, "narrowed"), (-1.0, -2.0, "narrowed"),
    (1.0, -1.0, "crossed"), (-0.0001, 0.0002, "crossed"), (1.5, 1.5, "unchanged"),
])
def test_macd_change_since_the_previous_bar(hist, prev, change):
    out = read("macd", (12, 26, 9), macd(100.0, 100.0 - hist, hist, prev), [1, 2])
    assert out.endswith(G["indicators"]["macd"]["readings"][change].format(unit="day")), out


def test_macd_zero_gap_or_missing_previous_bar_has_no_change_sentence():
    for values in (macd(100.0, 100.0, 0.0, 1.0), macd(100.0, 99.0, 1.0, 0.0), macd(100.0, 99.0, 1.0, None)):
        out = read("macd", (12, 26, 9), values, [1, 2])
        assert not any(w in out for w in ("widened", "narrowed", "crossed", "did not change")), out


def test_macd_line_side_and_signal_relation_use_unrounded_values():
    # MACD 0.004 (shows 0.00 at 2 decimals) is above zero and above a signal of 0.0035: 3 decimals keep both true
    out = read("macd", (12, 26, 9), macd(0.4, 0.35, 0.05), [1, 2])
    assert out.startswith("The MACD line is 0.004: above zero") and "It is above its signal line (0.003)." in out
    out = read("macd", (12, 26, 9), macd(-0.2, -0.2, 0.0), [1, 2])
    assert "below zero" in out and "It is level with its signal line (-0.002)." in out
    assert read("macd", (12, 26, 9), macd(0.0, None, None), [1, 2]).startswith("The MACD line is 0.00: at zero, so the "
                                                                               "12-day EMA is equal to the 26-day EMA.")


def test_macd_signal_not_ready_yet():
    out = read("macd", (12, 26, 9), macd(1341.0, None, None), [1, 2], "weekly")
    assert out == ("On the weekly view (completed weeks only): The MACD line is 13.41: above zero, so the 12-week EMA "
                   "is above the 26-week EMA. Its signal line needs 34 completed weeks: Not enough data yet.")


# ---- Not enough data, weekly prefix, Partial Week, Final Short Week ----

@pytest.mark.parametrize("kind,period,needed", [("sma", 20, 20), ("sma", 50, 50), ("ema", 12, 12), ("ema", 26, 26),
                                                ("rsi", 14, 15), ("macd", (12, 26, 9), 26)])
def test_not_enough_data_names_what_is_needed_and_what_exists(kind, period, needed):
    closes = list(range(1000, 1000 + needed - 1))  # one close too few
    values = ind.raw(kind, period, closes)
    name = explain.name_of(kind, period)
    assert read(kind, period, values, closes) == (
        f"{name} needs {needed} daily closes. This view has {needed - 1} so far, so it is not drawn yet.")
    assert read(kind, period, values, closes, "weekly") == (
        f"On the weekly view (completed weeks only): {name} needs {needed} completed weeks. This view has "
        f"{needed - 1} so far, so it is not drawn yet.")


def test_weekly_sentences_for_partial_and_final_short_weeks():
    v = {"sma": [18999.1]}
    assert read("sma", 20, v, [19996], "weekly", last_status="partial").endswith(" " + PARTIAL)
    assert read("sma", 20, v, [19996], "weekly", last_status="final_short", last_days=3).endswith(
        " The last week is the scenario's Final Short Week (3 trading days); it is complete and included.")
    assert PARTIAL not in read("sma", 20, v, [19996], "daily", last_status="partial")  # daily bars are never partial


def test_a_view_with_only_a_partial_week_has_no_completed_data():
    out = explain.reading("rsi", 14, {"rsi": []}, [], "weekly", "partial")
    assert out == ("On the weekly view (completed weeks only): RSI 14 needs 15 completed weeks. This view has 0 so far, "
                   "so it is not drawn yet. " + PARTIAL)


# ---- the approved text, kept word for word; no advice or prediction ----

def approved_doc():
    with open(os.path.join(ROOT, "docs", "P4_STEP6_CONTENT.md"), encoding="utf-8") as f:
        return re.sub(r"\s+", " ", f.read())


def all_text():
    out = [G["footer"], G["label"]] + [v for k, v in SHARED.items() if isinstance(v, str)]
    for entry in G["indicators"].values():
        out += [entry["what"], entry["how"], entry["watch"]] + list(entry["readings"].values())
    return out


def test_explanations_match_the_approved_document_word_for_word():
    doc = approved_doc()
    for kind, entry in G["indicators"].items():
        for part in ("what", "how", "watch"):
            assert entry[part] in doc, (kind, part)
    for key in ("weekly_prefix", "partial_week"):
        assert SHARED[key] in doc, key
    assert G["footer"] in doc and "Our plain summary" in doc


def test_every_preset_has_a_complete_entry_and_templates_fill_without_errors():
    for kind, periods in ind.PRESETS.items():
        entry = G["indicators"][kind]
        assert entry["what"] and entry["how"] and entry["watch"] and entry["readings"]
        for period in periods:
            for template in [entry["what"], *entry["readings"].values()]:
                template.format(close="1.00", value="1.00", n=period, unit="day", units="daily closes", macd="1.00",
                                signal="1.00")


BANNED = ["you should", "buy now", "sell now", "buy signal", "sell signal", "guaranteed", "sure thing", "will rise",
          "will fall", "time to buy", "time to sell", "bullish", "bearish", "we recommend", "i recommend", "best time"]


def test_no_advice_or_prediction_wording():
    for text in all_text():
        low = text.lower()
        for phrase in BANNED:
            assert phrase not in low, (phrase, text)
    assert "not a recommendation to buy or sell" in G["footer"]
    for text in all_text():  # "overbought" / "oversold" only ever as a label some people use
        if "overbought" in text or "oversold" in text:
            assert "some people call" in text or "often called" in text, text


# ---- the API carries the same sentences ----

def test_api_readings_equal_the_explainer_and_the_guide_route(client):
    from services import paper_engine as eng
    s = eng.new_state("synthetic-b")
    for d in range(160):
        s = eng.advance(s, d)
    body = {"state": s, "symbol": "SYN-TEC1", "timeframe": "daily", "indicators": [
        {"type": "sma", "period": 20}, {"type": "ema", "period": 12}, {"type": "rsi", "period": 14},
        {"type": "macd", "period": [12, 26, 9]}]}
    items = client.post("/api/analysis/indicators", json=body).get_json()["data"]["indicators"]
    assert [i["reading"] for i in items] == [
        "The latest close, $199.96, is above its 20-day average of $189.99.",
        "The latest close, $199.96, is above its 12-day EMA of $188.90.",
        "RSI is 56.1, between 30 and 70. Recently, average gains have been larger than average losses.",
        "The MACD line is -3.75: below zero, so the 12-day EMA is below the 26-day EMA. It is above its signal line "
        "(-5.81). The gap between them widened since the previous day.",
    ]
    weekly = client.post("/api/analysis/indicators", json=body | {"timeframe": "weekly"}).get_json()["data"]["indicators"]
    assert all(i["reading"].startswith(SHARED["weekly_prefix"]) and i["reading"].endswith(PARTIAL) for i in weekly)
    assert "Its signal line needs 34 completed weeks: Not enough data yet." in weekly[3]["reading"]
    env = client.get("/api/analysis/guide").get_json()
    assert env["ok"] and env["data"] == json.load(open(explain.GUIDE_PATH, encoding="utf-8"))
