"""Brokerage & Investing Accounts 101: 13 entries, categories, length, official sources, static copy only."""
import os
import re

JS_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "js", "accounts.js")
EXPECTED = {
    "Everyday brokerage": ["Individual taxable brokerage", "Joint taxable brokerage", "Cash brokerage", "Margin brokerage"],
    "Family and estate": ["Custodial UGMA/UTMA", "Trust brokerage"],
    "Retirement": ["Traditional IRA", "Roth IRA", "SEP IRA", "SIMPLE IRA"],
    "Education and healthcare": ["529 education savings plan", "Coverdell Education Savings Account",
                                 "Health Savings Account (HSA)"],
}
OFFICIAL = ("https://www.investor.gov/", "https://www.finra.org/", "https://www.irs.gov/")
ENTRY = re.compile(r'\[\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*\[([^\]]*)\]\s*\]')
CATEGORY = re.compile(r'\[\s*"([^"]+)",\s*\[\s*\n\s*\["')


def source():
    with open(JS_PATH, encoding="utf-8") as f:
        return f.read()


def entries():
    text = source()
    cats = [(m.start(), m.group(1)) for m in CATEGORY.finditer(text)]
    out = []
    for m in ENTRY.finditer(text):
        cat = [name for pos, name in cats if pos < m.start()][-1]
        keys = re.findall(r'"([a-z0-9_]+)"', m.group(5))
        out.append({"category": cat, "name": m.group(1), "how": m.group(2), "use": m.group(3), "watch": m.group(4), "keys": keys})
    return out


def sources():
    return dict(re.findall(r'(\w+): \["[^"]+", "(https://[^"]+)"\]', source()))


def test_exactly_13_entries_in_the_right_categories_and_order():
    got = {}
    for e in entries():
        got.setdefault(e["category"], []).append(e["name"])
    assert got == EXPECTED
    assert sum(len(v) for v in got.values()) == 13


def test_each_entry_explains_use_and_a_consideration_within_100_words():
    for e in entries():
        words = len(" ".join([e["how"], e["use"], e["watch"]]).split())
        assert 25 <= words <= 100, (e["name"], words)


def test_every_entry_links_only_verified_official_sources():
    urls = sources()
    assert len(urls) == 17
    assert all(u.startswith(OFFICIAL) for u in urls.values())
    for e in entries():
        assert e["keys"], e["name"]
        assert all(k in urls for k in e["keys"]), e["name"]
    assert 'rel = "noopener noreferrer"' in source() and 'target = "_blank"' in source()


def test_copy_is_static_with_no_figures_or_advice():
    text = source()
    assert "fetch(" not in text and "window.Api" not in text and "innerHTML" not in text
    for e in entries():
        body = " ".join([e["how"], e["use"], e["watch"]])
        assert not re.search(r"\d|\$|%", body), e["name"]  # no contribution limits, ages or other figures
        assert not re.search(r"\byou should\b|\brecommend|\bbest\b|\bsafe\b", body, re.I), e["name"]


def test_intro_states_overlap_and_the_static_notice():
    text = source()
    assert "These are 13 commonly encountered account types or arrangements, not 13 exclusive official categories." in text
    assert "an individual or joint account is also either a cash or a margin account" in text
    assert "Static educational content — not AI-generated. Not tax, legal or investment advice." in text


def test_button_container_and_script_order(client):
    html = client.get("/").get_data(as_text=True)
    header = html[html.index('<header class="app-header">'):html.index("</header>")]
    assert 'id="accounts-open"' in header and "Learn about accounts" in header
    assert 'id="accounts-root"' in html and 'id="disclaimer-footer"' in html
    assert html.index("/static/js/risk_education.js") < html.index("/static/js/accounts.js") < html.index("/static/js/app.js")
