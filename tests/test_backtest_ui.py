"""Test a strategy view (P5 step 6): page wiring, what the browser may send, isolation from the practice account, and
wording taken from the owner-approved docs/P5_CONTENT.md. The behaviour itself is checked in a real browser by
scripts/qa/backtest.mjs; these static checks keep the guarantees from regressing."""
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def js():
    return read("static", "js", "backtest.js")


def text():
    return re.sub(r'"\s*\+\s*"', "", js())  # page text with string concatenations joined


def content():
    return re.sub(r"\s+", " ", read("docs", "P5_CONTENT.md"))


def test_the_script_loads_after_the_chart_library_and_before_paper_js(client):
    html = client.get("/").get_data(as_text=True)
    order = [html.index(s) for s in ("/static/vendor/lightweight-charts/", "/static/js/backtest.js",
                                     "/static/js/paper.js", "/static/js/app.js")]
    assert order == sorted(order)


def test_the_only_request_is_the_read_only_backtest_with_four_fields():
    source = js()
    assert "fetch(" not in source and "XMLHttpRequest" not in source and "paperPost" not in source
    calls = re.findall(r"window\.Api\.postBacktest\(\{([^}]*)\}\)", source)
    assert len(calls) == 1 and source.count("postBacktest(") == 1
    assert set(re.findall(r"(\w+):", calls[0])) == {"state", "symbol", "preset", "costs"}
    assert 'request("/api/backtest/run"' in read("static", "js", "api.js")


def test_the_view_never_touches_the_saved_session_or_writes_html():
    source = js()
    assert "localStorage" not in source and "sessionStorage" not in source and "writeSession" not in source
    assert "innerHTML" not in source and "insertAdjacentHTML" not in source  # text only, so names cannot inject markup


def test_paper_js_only_adds_the_view_switch():
    paper = read("static", "js", "paper.js")
    assert "postBacktest" not in paper and "/api/backtest" not in paper
    assert 'group.setAttribute("aria-label", "Practice Trading view")' in paper
    assert '[["trade", "Trade"], ["strategy", "Test a strategy"]]' in paper
    assert "window.Backtest.mount(regions.setup, regions.strategy, {" in paper


APPROVED = [
    "Replay a fixed rule on the days you have reached, next to buying and holding the same ticker.",
    "Buys when the 20-day average crosses above the 50-day average; sells when it crosses back below.",
    "Buys when RSI 14 closes below 30; sells when it closes above 70.",
    "Your practice account is not changed.",
    "This is a hypothetical test on computer-generated prices. A rule that did well here can do badly on other prices. "
    "Past results, real or simulated, do not tell you what will happen next.",
    "This only describes what happened in two stretches of synthetic prices. It is not evidence that the rule works, "
    "and neither half tells you how the other, or any later stretch, will go.",
    "The same rule, tested again on each half from a fresh $10,000.",
    "Available from Day 130.",
    "A backtest replays a fixed rule on prices that have already happened and reports what that rule would have done.",
    "but a fixed rule is still only being tested on one set of prices.",
    "rounded to the cent against the trader. No commission.",
    "No costs: every fill is at the opening price exactly. Real trading usually has some cost.",
    "Cash left over after buying whole shares stays as cash.",
    "the test and buy and hold both start at the Day 50 close.",
    "Only days you have reached in Practice Trading are used. Your practice account, orders and cash are not changed.",
    "The first crossing the test can see is on Day 51, so its first fill can be at the Day 52 open.",
    "uses the same Day 50 start as the crossover rule so every test covers the same days.",
    "No trades: the rule never triggered",
    "The 20-day average did not cross above the 50-day average from the Day 50 close to ",
    "The test starts in cash and waits for a fresh crossing. It does not assume a trade happened before the Day 50 close.",
    "Nothing is estimated in the meantime.",
    "They were not sold, so no further cost was charged.",
    "Not acted on, because there is no next open yet.",
    "Your practice session is unchanged.",
    "The money stayed in cash.",
    "nothing is invested and no return is counted for them.",
    "The practice day changed, so the previous result was cleared. Run the test again to include the new day.",
]


@pytest.mark.parametrize("sentence", APPROVED)
def test_wording_comes_from_the_approved_content(sentence):
    assert sentence in text(), sentence
    assert sentence in content(), sentence


def test_metric_names_follow_the_approved_corrections():
    t = text()
    assert '"Daily volatility"' in t and "Typical daily move" not in t
    assert '"Largest drop from a high"' in t and '"Days invested"' in t and '"Costs paid"' in t
    assert "In: bought" in t and "Out: sold" in t


def test_no_advice_prediction_or_ranking_words():
    t = text()
    for allowed in ("what will happen next", "or any later stretch, will go"):
        t = t.replace(allowed, "")
    for word in ("will", "expect", "predict", "best", "winning", "outperform", "beat the market", "guaranteed",
                 "you should", "buy now", "sell now", "sure thing", "buy signal", "sell signal", "bullish", "bearish",
                 "recommend", "in-sample", "out-of-sample"):
        assert not re.search(r"\b" + re.escape(word) + r"\b", t, re.I), word


def mockup_09():
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", read("docs", "mockups", "09-strategy-desktop.html")))


@pytest.mark.parametrize("phrase", [
    "Prices, the rule's fills and the value of $10,000", "Days 1–50: price history for indicators only",
    "Day 50 close: results start", "The shaded Days 1–50 are price history for the",
    "results are measured from the Day 50 close.", "SMA 20 (solid) and SMA 50 (dashed) over the prices;",
    "Below, the value of $10,000: this rule (solid) ended at", "Prices and values shown are simulated.",
])
def test_chart_wording_follows_the_approved_mockup(phrase):
    assert phrase in text() and phrase in mockup_09(), phrase


@pytest.mark.parametrize("phrase", [
    "RSI 14 in a pane below the prices, with guides at 30 and 70; ", "the rule made no fills on these days.",
    "Not filled marks an entry the cash did not cover.", "A signal on the last day, not acted on, is marked on the last day.",
    '"Signal, not acted on"', '"Not filled"',
])
def test_chart_lines_beyond_the_mockup_are_listed_for_approval(phrase):
    addendum = content()[content().index("Step 7 addendum"):]
    assert phrase in text() and phrase.strip('"').strip() in addendum, phrase


def test_the_chart_draws_only_the_reply_and_marks_fills_on_their_own_day():
    source = js()
    assert "LC.createChart(chartBox.canvas" in source and source.count("createChart(") == 1
    assert 'r.strategy.values.map(function (v) { return { time: v.time, value: v.value_cents / 100 }; })' in source
    assert 'r.benchmark.values.map(function (v) { return { time: v.time, value: v.value_cents / 100 }; })' in source
    assert 'return { time: f.date, position: buy ? "belowBar" : "aboveBar"' in source  # the fill day, not signal_date
    chart_code = source[source.index("function drawChart()"):source.index("function redrawForTheme()")]
    # the chart is pointer-only (recorded for the step 9 accessibility audit); its text version is the alternative
    assert 'canvas.setAttribute("aria-hidden", "true")' in source and "keydown" not in chart_code



def test_the_cards_use_the_approved_footer_titles_and_labels():
    from services import strategy_guide
    g, t = strategy_guide.load(), text()
    assert '"' + g["footer"] + '"' in t  # the footer also shows while the guide is unavailable
    titles = {k: m["title"] for k, m in g["metrics"].items()} | {"buy_hold": g["buy_hold"]["title"]}
    for key, title in titles.items():
        assert f'{key}: "{title}"' in t, key
    for label in ("What it does", "Why people test it", "Why it is here", "What it shows", "How it is worked out",
                  "Watch out", "How it works", "Our plain summary"):
        assert label in content(), label
    assert "window.Api.getBacktestGuide()" in t and 'request("/api/backtest/guide")' in read("static", "js", "api.js")
    assert 'b.setAttribute("aria-expanded"' in t and 'b.setAttribute("aria-controls", box.id)' in t
    assert 'summary.setAttribute("aria-label", "Learn more about " + about)' in t
