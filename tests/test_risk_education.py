"""Static risk education panel: placement, exact copy and attribution, no network calls, no figures."""
import os
import re

JS_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "js", "risk_education.js")
SLIDES = "https://privatewealth.goldmansachs.com/semester-with-goldman-sachs-2025-session-5-slides.pdf"
ONE_PAGER = "https://privatewealth.goldmansachs.com/semester-with-goldman-sachs-2025-session-5-one-pager.pdf"
COPY = [
    "Understanding risk tolerance",
    "Low — Conservative",
    "Focuses on financial stability, limiting potential losses, and understanding uncertainty.",
    "Medium — Moderate",
    "Balances potential growth with financial stability and the possibility of losses.",
    "High — Aggressive",
    "Considers growth opportunities alongside greater volatility and the possibility of larger losses.",
    "Based on Goldman Sachs Private Wealth Management educational materials (2025).",
    "Static educational content — not AI-generated.",
    "Not affiliated with or endorsed by Goldman Sachs.",
    "These are general portfolio concepts, not risk ratings for any particular company or personalized investment advice.",
]


def js():
    with open(JS_PATH, encoding="utf-8") as f:
        return f.read()


def test_panel_container_in_sidebar_and_script_before_app(client):
    html = client.get("/").get_data(as_text=True)
    sidebar = html[html.index('class="card col-watchlist"'):html.index("</aside>")]
    assert 'id="risk-education"' in sidebar
    assert html.index("/static/js/risk_education.js") < html.index("/static/js/app.js")
    assert html.index("/static/js/checklist.js") < html.index("/static/js/risk_education.js")


def test_exact_copy_and_both_source_links():
    text = js()
    for line in COPY:
        assert line in text, line
    assert SLIDES in text and ONE_PAGER in text
    assert 'rel = "noopener noreferrer"' in text and 'target = "_blank"' in text


def test_panel_is_static_with_no_figures_or_ai():
    text = js()
    assert "fetch(" not in text and "window.Api" not in text and "innerHTML" not in text
    shown = " ".join(COPY)
    # No volatility, allocation or return figures: the only digits shown are the publication year.
    assert "%" not in text and not re.search(r"\d", shown.replace("(2025)", ""))
    assert "official" not in text.lower() and "safe" not in shown.lower()
