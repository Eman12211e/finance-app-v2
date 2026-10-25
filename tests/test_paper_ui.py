"""Practice Trading tab (P2): page wiring, labelling, privacy of journal notes and safe rendering. The behaviour is
also checked in a real browser before release; these static checks keep the guarantees from regressing."""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def js():
    return read("static", "js", "paper.js")


def text():
    return re.sub(r'"\s*\+\s*"', "", js())  # page text with string concatenations joined


def test_page_has_the_practice_trading_tab_and_scripts_in_order(client):
    html = client.get("/").get_data(as_text=True)
    assert 'data-tab="paper"' in html and 'id="paper-root"' in html
    assert html.index("/static/js/brokers.js") < html.index("/static/js/paper.js") < html.index("/static/js/app.js")
    assert 'paper: ["paper-root", window.Paper]' in read("static", "js", "app.js")
    assert [t for t in re.findall(r'data-tab="(\w+)"', html)] == ["explore", "lab", "sign", "brokers", "paper"]


def test_only_session_and_order_numbers_are_ever_sent_to_the_server():
    calls = re.findall(r'call\("(\w+)", \{([^}]*)\}', js())
    assert {c[0] for c in calls} == {"new", "view", "preview", "confirm", "cancel", "advance"}
    for _, body in calls:
        keys = set(re.findall(r"(\w+):", body))
        assert keys <= {"scenario", "state", "order", "order_id", "expected_day"}, keys
    sent_order = re.search(r"var order = \{ id: d\.id, ([^}]*)\}", js()).group(1)
    assert set(re.findall(r"(\w+):", sent_order)) == {"symbol", "side", "shares"}
    assert "paperPost(path, body)" in js() and js().count("paperPost(") == 1


def test_journal_text_is_kept_in_browser_storage_only():
    code = js()
    assert "saveJournalNote(d.id, why, risks);  // stored locally only" in code
    assert "JOURNAL_KEY" in code and 'maxLength = 280' in code
    assert "Saved only in this browser and never sent anywhere." in text()


def test_renders_safely_and_collects_no_sensitive_data():
    code = js()
    for banned in ("innerHTML", "fetch(", "document.cookie", "XMLHttpRequest", "eval(", '"password"', '"file"', '"email"'):
        assert banned not in code, banned


def test_every_view_carries_the_simulation_labels():
    t = text()
    assert "SIMULATED PRACTICE: not real money, prices or trades" in t
    assert "no real securities are bought or sold" in t
    assert "leaves out fees, the bid-ask spread, slippage and market impact" in t
    assert "Market orders fill at the next simulated day's opening price, which can differ from the preview." in t


def test_damaged_sessions_are_reported_not_replaced():
    t = text()
    assert "Your saved practice session could not be opened" in t and "It has not been replaced." in t
    assert 'env.error.code === "INVALID_STATE"' in js()


def test_reset_needs_explicit_confirmation():
    t = text()
    assert "Reset the simulation? This deletes your practice session and journal notes from this browser" in t
    assert '"Yes, reset"' in js() and '"Keep my session"' in js()


def test_double_clicks_and_stale_tabs_are_guarded():
    code = js()
    assert "if (busy) return;" in code and "draft = data.ok ? { id: newOrderId()" in code  # one id per previewed order
    assert "Your practice session changed in another tab, so it was reloaded." in text()


def test_storage_and_education_notes_and_links():
    t = text()
    assert "Clearing site data deletes them, and anyone using the same browser profile can see them." in t
    assert 'window.Accounts.open("Cash brokerage")' in js() and "window.Sign.openAt(g[1], g[2])" in js()


def test_layout_stacks_on_phones():
    css = read("static", "css", "features.css")
    section = css.split("/* ---- Practice Trading ---- */")[1]
    assert ".pt-layout { grid-template-columns: minmax(0, 1fr); }" in section and "overflow-x" not in section
