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
