"""P2.5 design system and app shell: tokens, dark theme, fonts, header and accessible tabs. Static, offline checks;
the look itself is checked in a browser by the owner."""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def css():
    return read("static", "css", "style.css")


def root_block(text):
    return text[text.index(":root {"):text.index("}", text.index(":root {"))]


def test_required_tokens_are_defined():
    block = root_block(css())
    for name in ("bg", "surface", "surface-2", "text", "muted", "border", "accent", "accent-hover", "up", "down", "warning",
                 "s-1", "s-2", "s-3", "s-4", "s-5", "s-6", "s-7", "t-12", "t-14", "t-16", "t-20", "t-24", "t-32",
                 "r-8", "r-12", "r-16", "shadow-1", "shadow-2", "m-fast", "m-slow", "font-display", "font-text"):
        assert f"--{name}:" in block, name
    for size, token in (("4px", "s-1"), ("48px", "s-7"), ("12px", "t-12"), ("32px", "t-32"), ("150ms", "m-fast"), ("250ms", "m-slow")):
        assert f"--{token}: {size}" in block


def test_old_token_names_are_gone():
    for f in ("style.css", "features.css"):
        assert not re.search(r"var\(--(accent-soft|error|radius|gap|font)\)", read("static", "css", f)), f


def test_dark_theme_follows_the_system_and_can_be_overridden():
    text = css()
    assert '@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"]) {' in text
    assert ':root[data-theme="dark"] {' in text
    dark = text[text.index(':root[data-theme="dark"] {'):]
    for name in ("bg", "surface", "text", "muted", "accent", "up", "down", "warning", "on-accent"):
        assert f"--{name}:" in dark[:dark.index("}")], name


def test_theme_choice_is_applied_before_paint_and_storage_is_guarded():
    html = read("templates", "index.html")
    head = html[:html.index("</head>")]
    assert '<script src="/static/js/theme.js"></script>' in head  # not deferred: runs before first paint
    assert head.index("theme.js") < head.index("style.css")
    js = read("static", "js", "theme.js")
    assert js.count("try {") == 2 and "localStorage" in js and "innerHTML" not in js
    assert 'id="theme-toggle"' in html


FONTS = {"public-sans": "PublicSans-latin-wght.woff2", "bricolage-grotesque": "BricolageGrotesque-latin-700.woff2"}


def test_fonts_are_self_hosted_woff2_with_their_ofl_licence():
    for folder, name in FONTS.items():
        base = os.path.join(ROOT, "static", "fonts", folder)
        with open(os.path.join(base, name), "rb") as f:
            assert f.read(4) == b"wOF2", name
        licence = read("static", "fonts", folder, "OFL.txt")
        assert "SIL Open Font License, Version 1.1" in licence, folder
        assert f'url("/static/fonts/{folder}/{name}") format("woff2")' in css()


def test_css_comments_are_well_formed():
    # a "*/" inside a comment (for example a path like fonts/*/x) silently ends it and breaks the next rule
    for f in os.listdir(os.path.join(ROOT, "static", "css")):
        text = read("static", "css", f)
        assert re.sub(r"/\*.*?\*/", "", text, flags=re.S).count("*/") == 0, f


def test_font_roles_follow_the_approved_split():
    text = css()
    assert 'font-family: "Public Sans"; font-style: normal; font-weight: 400 700;' in text
    assert 'font-family: "Bricolage Grotesque"; font-style: normal; font-weight: 700;' in text
    assert "--font-display: \"Bricolage Grotesque\"" in text and "--font-text: \"Public Sans\"" in text
    assert "font-variant-numeric: tabular-nums;" in text[text.index("body {"):text.index("}", text.index("body {"))]


EXTERNAL = re.compile(r"https?://(?!127\.0\.0\.1|localhost)|//fonts\.googleapis|//fonts\.gstatic|cdn\.|unpkg|jsdelivr|cdnjs",
                      re.IGNORECASE)


def test_no_template_css_or_js_loads_from_a_third_party_host():
    files = [("templates", "index.html")] + [("static", "css", f) for f in os.listdir(os.path.join(ROOT, "static", "css"))]
    files += [("static", "js", f) for f in os.listdir(os.path.join(ROOT, "static", "js")) if f.endswith(".js")]
    for parts in files:
        text = read(*parts)
        # links shown to people (href to official sources) are fine; loading resources from other hosts is not
        loads = re.findall(r'(?:src|@import|url)\s*[=(]\s*["\']?([^"\')\s]+)', text)
        bad = [u for u in loads if EXTERNAL.search(u)]
        assert not bad, (parts, bad)


def header():
    html = read("templates", "index.html")
    return html[html.index('<header class="app-header">'):html.index("</header>")]


def test_header_has_brand_five_icon_tabs_one_learn_menu_and_profile():
    h = header()
    assert h.index('class="brand"') < h.index('class="tabs"') < h.index('id="learn-button"') < h.index('id="profile-chip"')
    assert h.count('class="tab-icon"') == 5 and h.count('<svg class="tab-icon"') == 5  # inline SVG, no icon library
    menu = h[h.index('id="learn-menu"'):h.index("</ul>", h.index('id="learn-menu"'))]
    for item_id, label in (("checklist-open", "Before you buy"), ("accounts-open", "Learn about accounts"), ("sentiment-open", "Sentiment")):
        assert f'id="{item_id}"' in menu and f">{label}</button>" in menu
    assert 'aria-haspopup="true"' in h and 'aria-expanded="false"' in h and 'role="menu"' in menu


def test_phone_labels_are_part_of_each_tab_name():
    # WCAG label-in-name: the short label shown on phones must appear in the full accessible name
    h = header()
    import re as _re
    for full, short in _re.findall(r'<span class="tab-label">([^<]+)</span><span class="tab-short" aria-hidden="true">([^<]+)</span>', h):
        assert short in full, (short, full)


def test_learn_menu_is_keyboard_operable():
    js = read("static", "js", "app.js")
    for key in ('"ArrowDown"', '"ArrowUp"', '"Home"', '"End"', '"Escape"', '"Tab"'):
        assert key in js
    assert "learnButton.focus();" in js


def test_tabs_are_a_real_tablist_with_hash_routing():
    html = read("templates", "index.html")
    assert html.count('role="tablist"') == 1 and html.count('role="tab" ') == 5 and html.count('role="tabpanel"') == 5
    panels = {"explore": "explore-view", "lab": "lab-root", "sign": "sign-root", "brokers": "brokers-root", "paper": "paper-root"}
    for key, panel in panels.items():
        assert f'id="tab-{key}" data-tab="{key}" aria-controls="{panel}"' in html, key
        assert f'id="{panel}"' in html and f'aria-labelledby="tab-{key}"' in html, key
    assert html.count('aria-selected="true"') == 1 and html.count('tabindex="0"') == 1  # roving tabindex
    js = read("static", "js", "app.js")
    assert 'paper: "practice"' in js and "history.pushState" in js and '"popstate"' in js and '"hashchange"' in js
    for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
        assert key in js
    assert "showTab(tabFromHash());" in js


def test_chat_styles_use_theme_tokens_so_dark_mode_stays_readable():
    js = read("static", "js", "chat.js")
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", js)  # hard-coded light colours made dark-mode chat text invisible


def test_phone_footer_rule_comes_after_the_base_rule():
    css = read("static", "css", "style.css")
    base = css.index("#disclaimer-footer {\n  position: sticky; bottom: 0;".replace("\n", "\r\n" if "\r\n" in css else "\n"))
    assert css.index("#disclaimer-footer { bottom: 64px;") > base  # otherwise bottom: 0 hides it behind the phone tabs
