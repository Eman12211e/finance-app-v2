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
    assert {c[0] for c in calls} == {"new", "view", "market", "preview", "confirm", "cancel", "advance"}
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


# ---- P2.5 step 5: final validation of the app shell, the layout and both practice markets ----

def test_served_page_has_an_accessible_five_tab_tablist_with_hash_routing(client):
    html = client.get("/").get_data(as_text=True)
    tablist = re.search(r'<div class="tabs" role="tablist" aria-label="Sections">(.*?)</div>', html, re.S).group(1)
    tabs = re.findall(r'role="tab" id="tab-(\w+)" data-tab="\1" aria-controls="([\w-]+)"', tablist)
    assert [t[0] for t in tabs] == ["explore", "lab", "sign", "brokers", "paper"]
    for key, panel in tabs:
        assert re.search(rf'id="{panel}"[^>]*role="tabpanel" aria-labelledby="tab-{key}"', html), key
    hashes = re.search(r"var HASHES = \{([^}]*)\}", read("static", "js", "app.js")).group(1)
    assert set(re.findall(r"(\w+):", hashes)) == {t[0] for t in tabs}  # every tab has a URL hash


def test_layout_rules_cover_390px_phones_and_1280px_desktops(client):
    # Static check by design (no Playwright): the owner's playtest and a headless-browser run confirm the pixels.
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in client.get("/").get_data(as_text=True)
    style, features = read("static", "css", "style.css"), read("static", "css", "features.css")
    assert "@media (max-width: 640px)" in style and "grid-template-columns: repeat(5, 1fr)" in style  # 390: bottom bar
    assert "@media (min-width: 641px) and (max-width: 1400px)" in style  # 1280: tabs on their own row
    practice = features.split("/* ---- Practice Trading ---- */")[1]
    assert "grid-template-columns: 240px minmax(0, 1fr) 320px;" in practice  # 1280: three regions
    assert ".pt-ticket.pt-open {" in practice and ".pt-trade-bar { display: block;" in practice  # 390: bottom sheet
    for css in (style, features):
        for value in re.findall(r"(?<![-\w])(?:min-)?width:\s*(\d+)px\s*[;}]", css):  # declarations, not media queries
            assert int(value) <= 358, value  # nothing fixed wider than a 390px screen minus 16px gutters


def test_journal_notes_never_reach_a_request():
    code = js()
    for _, body in re.findall(r'call\("(\w+)", \{([^}]*)\}', code):
        assert "journal" not in body.lower() and "why" not in body and "risks" not in body
    assert "journal" not in read("static", "js", "api.js").lower()
    assert code.count("JOURNAL_KEY") == 4  # declared, read, written, cleared: localStorage only


def scripts_module():
    import sys
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import build_synthetic_scenario
    return build_synthetic_scenario


def strict_json(*parts):
    import json

    def reject(token):
        raise ValueError(f"non-finite number {token} in {parts[-1]}")
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return json.load(f, parse_constant=reject)


def test_synthetic_b_has_12_fictional_tickers_in_6_sectors_over_250_trading_days():
    from datetime import date
    m = strict_json("data", "paper", "scenarios", "synthetic-b.json")
    assert m["kind"] == "synthetic" and "Not real market data" in m["notice"]
    assert len(m["symbols"]) == 12 and set(m["bars"]) == set(m["symbols"])
    assert all(s.startswith("SYN-") and v["name"].endswith("(fictional)") for s, v in m["symbols"].items())
    real = set(strict_json("data", "demo_stocks.json")["tickers"])
    assert not real & set(m["symbols"])
    sectors = [v["sector"] for v in m["symbols"].values()]
    assert len(set(sectors)) == 6 == len(m["sectors"]) and all(sectors.count(s) == 2 for s in m["sectors"])
    days = [date.fromisoformat(d) for d in m["dates"]]
    assert len(days) == 250 and days == sorted(set(days)) and all(d.weekday() < 5 for d in days)


def test_every_synthetic_b_bar_is_valid_finite_and_reproducible():
    gen = scripts_module()
    m = strict_json("data", "paper", "scenarios", "synthetic-b.json")
    for symbol, bars in m["bars"].items():
        assert len(bars) == 250, symbol
        for b in bars:
            assert set(b) == {"o", "h", "l", "c", "v"}
            assert all(type(b[k]) is int and b[k] > 0 for k in b), (symbol, b)  # integer cents: never NaN or inf
            assert b["l"] <= min(b["o"], b["c"]) <= max(b["o"], b["c"]) <= b["h"], (symbol, b)
    assert gen.build_b() == gen.build_b() == m  # same seed, same market
    assert gen.build_b(seed=gen.SEED_B + 1) != m
    gap, down = m["events"]
    tec = m["bars"][gap["symbol"]]
    assert tec[gap["day"]]["o"] / tec[gap["day"] - 1]["c"] > 1.1
    moves = [m["bars"][s][down["to_day"]]["c"] / m["bars"][s][down["from_day"] - 1]["c"] for s in m["bars"]]
    assert sum(moves) / len(moves) < 0.9


def test_synthetic_a_stays_byte_compatible_and_existing_sessions_still_load():
    import hashlib
    import json
    from services import paper_engine as eng
    gen = scripts_module()
    m = strict_json("data", "paper", "scenarios", "synthetic-a.json")
    assert gen.build() == m and set(m["symbols"]) == {"SAMPLE-A", "SAMPLE-B"} and len(m["dates"]) == 120
    digest = hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()
    assert digest == "57783a19aede54bf7fd42adfea4955f03bb798e6ce9e771ab258c385738b81e0"  # unchanged since P2
    order = {"id": "order-0001", "symbol": "SAMPLE-A", "side": "buy", "shares": 5, "placed_day": 0,
             "status": "filled", "reason": None, "fill_day": 1}
    saved = eng._sign({"schema": 1, "scenario": "synthetic-a", "day": 1, "ended": False, "orders": [order]})
    view = eng.view(saved)
    assert view["scenario"]["id"] == "synthetic-a"
    assert view["portfolio"]["cash_cents"] == 1_000_000 - 5 * m["bars"]["SAMPLE-A"][1]["o"]
    assert "view ? view.scenario.id : scenarioId" in js()  # Reset keeps a saved session's market


# ---- P2.5 step 3: the rebuilt Practice Trading workspace (behaviour checked in a headless browser before release) ----

def test_workspace_is_built_once_and_actions_redraw_only_their_regions():
    code = js()
    assert code.count('root.textContent = ""') == 4  # workspace, start, damaged and loading screens only
    assert code.count("buildWorkspace()") == 2  # its definition and one call, from load()
    assert "function render(" not in code
    for region in ("strip", "watch", "chart", "positions", "pending", "history"):
        assert f"RENDER.{region} = function" in code, region
    assert "data-key" in code and "focusKey" in code  # focus returns to the same control after a redraw


def test_three_regions_chart_placeholder_and_header_day_controls():
    code, t = js(), text()
    assert "layout.appendChild(regions.watch);" in code and "layout.appendChild(regions.ticket);" in code
    assert "RENDER.chart = function" in code and "Chart timeframe" in t
    assert '"Next day", 1], ["Next 5 days", 5]' in code and '"role", "progressbar"' in code
    assert '"aria-valuetext", "Day " + (day.index + 1) + " of " + total' in code


def test_order_ticket_controls_are_accessible():
    code = js()
    assert '"role", "combobox"' in code and '"role", "listbox"' in code and "aria-activedescendant" in code
    assert '"aria-label", "Order side"' in code and '"aria-pressed"' in code
    assert '"One share fewer"' in code and '"One share more"' in code and '"Max"' in code
    assert 'shares.inputMode = "numeric"' in code
    # Max mirrors the engine's preview checks (cash after pending buys; held minus pending sells)
    assert "view.portfolio.cash_cents - reserved" in code and "held - selling" in code


def test_preview_confirm_and_back_swap_the_ticket_body_in_place():
    code, t = js(), text()
    for title in ("Check your practice order", "Order queued", "Practice order"):
        assert f'"{title}"' in t, title
    assert 'ui.mode = "review";' in code and 'ui.mode = "queued";' in code
    assert "Back keeps ticker, side and shares; nothing was sent" in code


def test_fills_are_announced_and_rows_flash():
    code = js()
    assert 'regions.toasts.setAttribute("role", "status")' in code
    assert 'regions.toasts.setAttribute("aria-atomic", "false")' in code
    assert "setTimeout(function () { t.remove(); }, 5000);" in code and '"Dismiss notification"' in code
    css = read("static", "css", "features.css")
    assert "@keyframes pt-flash" in css and "@media (prefers-reduced-motion: reduce)" in css


def test_phone_trade_sheet_is_a_modal_dialog_closed_by_escape():
    code = js()
    assert 'PHONE = window.matchMedia("(max-width: 720px)")' in code
    assert 't.setAttribute("role", "dialog")' in code and 't.setAttribute("aria-modal", "true")' in code
    assert 'if (e.key === "Escape") {\n      closeSheet();' in code and '"Close trade sheet"' in code
    assert "keep Tab inside the open sheet" in code


def test_positions_history_sectors_and_simulated_labels():
    code, t = js(), text()
    assert '["Ticker", "Shares", "Avg cost", "Last", "Market value", "Unrealized"]' in code
    assert 'el("details", "card pt-history")' in code and '"All tickers"' in code
    assert "info(s).sector" in code and '"pt-sector"' in code  # synthetic-b groups the watchlist by sector
    assert code.count("sim()") >= 4  # strip, watchlist, positions, ticket
    css = read("static", "css", "features.css")
    assert r'.pt-up::before { content: "\25B2' in css and r'.pt-down::before { content: "\25BC' in css  # not colour alone


def test_scenario_notice_shown_and_market_can_be_changed_after_confirming():
    code, t = js(), text()
    assert 'view.scenario.label + ": " + view.scenario.notice' in code
    assert '"Change practice market"' in code and '"Yes, change market"' in code
    assert "Change the practice market? This deletes your practice session and journal notes" in t
    assert code.count("clearAll();") == 2  # new session, change market: both only after an explicit confirm


# ---- P3: price chart (behaviour, weekly bars and both themes checked in a headless browser before release) ----

def test_chart_uses_the_vendored_library_loaded_before_the_tab(client):
    html = client.get("/").get_data(as_text=True)
    vendor = "/static/vendor/lightweight-charts/lightweight-charts.standalone.production.js"
    assert html.index(vendor) < html.index("/static/js/paper.js")
    code = js()
    assert "window.LightweightCharts" in code and "LC.CandlestickSeries" in code and "LC.HistogramSeries" in code
    assert "The chart could not load." in text()  # the tab still works if the script is missing


def test_chart_only_draws_bars_the_server_sent_for_today_and_marks_your_trades():
    code = js()
    assert "var daily = market.bars[symbol];" in code and "if (!LC || !marketIsCurrent())" in code
    assert "view.portfolio.transactions.filter(function (t) { return t.symbol === symbol; })" in code
    assert '"arrowUp"' in code and '"arrowDown"' in code and "LC.createSeriesMarkers(candles, marks)" in code


def test_chart_is_accessible_credited_and_follows_the_theme():
    code, t = js(), text()
    assert 'canvas.setAttribute("aria-hidden", "true");' in code and "summary.textContent" in code
    assert "Scroll or pinch to zoom and drag to move through time." in t
    assert "attributionLogo: false" in code and 'link.href = "https://www.tradingview.com/";' in code
    assert 'link.rel = "noopener noreferrer";' in code
    assert 'attributeFilter: ["data-theme"]' in code and "prefers-color-scheme: dark" in code
    assert "vertTouchDrag: false" in code  # phones can still scroll past the chart
    assert '[["daily", "Daily"], ["weekly", "Weekly"]]' in code
