import copy

import pytest

from services import ai_service
from services.earnings_service import ETF_MESSAGE, attach_explanations, build_facts


def make_financials(**overrides):
    """Synthetic EXMPL financials. Fake numbers, tests only."""
    fin = {
        "ticker": "EXMPL",
        "name": "Example Corp",
        "is_etf": False,
        "quarters": [
            {"period_end": "2026-06-27", "revenue": 1.06e10, "net_income": 2.0e9, "cash_and_equivalents": 3.0e10},
            {"period_end": "2026-03-28", "revenue": 9.0e9, "net_income": 1.0e9, "cash_and_equivalents": 2.0e10},
            {"period_end": "2025-12-27", "revenue": 9.0e9, "net_income": 1.0e9, "cash_and_equivalents": 2.0e10},
            {"period_end": "2025-06-28", "revenue": 1.0e10, "net_income": 1.8e9, "cash_and_equivalents": 2.5e10},
        ],
        "eps": {"period_end": "2026-06-27", "report_date": "2026-07-30", "actual": 1.23, "estimate": 1.20},
        "dividend": {"pays_dividend": True, "last_amount": 0.25, "last_ex_date": "2026-08-10"},
        "next_earnings_date": "2026-10-30",
    }
    fin.update(overrides)
    return fin


def test_prior_year_found_at_364_days():
    facts = build_facts(make_financials(), "demo")
    rev = facts["sections"]["revenue"]
    assert rev["prior_year_value"]["value"] == 1.0e10
    assert rev["change_percent"]["display"] == "+6.0%"
    assert rev["direction"] == "up"
    assert facts["period"] == {"label": "Quarter ended Jun 27, 2026", "period_end": "2026-06-27"}


def test_prior_year_missing_when_only_182_days_back():
    fin = make_financials()
    fin["quarters"] = fin["quarters"][:1] + [fin["quarters"][2]]  # ~182 days back only
    rev = build_facts(fin, "demo")["sections"]["revenue"]
    assert rev["prior_year_value"] == {"value": None, "display": "Data not available"}
    assert rev["change_percent"]["value"] is None and rev["direction"] is None


def test_change_null_when_prior_is_zero():
    fin = make_financials()
    fin["quarters"][3]["revenue"] = 0
    assert build_facts(fin, "demo")["sections"]["revenue"]["change_percent"]["value"] is None


@pytest.mark.parametrize("current, expected", [(1.004e10, "flat"), (1.006e10, "up"), (0.994e10, "down")])
def test_direction_thresholds(current, expected):
    fin = make_financials()
    fin["quarters"][0]["revenue"] = current  # prior is 1.0e10 -> +0.4 / +0.6 / -0.6 %
    assert build_facts(fin, "demo")["sections"]["revenue"]["direction"] == expected


@pytest.mark.parametrize("actual, estimate, comparison, diff_display", [
    (1.23, 1.20, "above", "$0.03"),
    (1.20, 1.20, "equal", "$0.00"),
    (1.21, 1.20, "above", "$0.01"),  # float error must not make this "equal"
    (1.19, 1.20, "below", "-$0.01"),
])
def test_eps_comparison(actual, estimate, comparison, diff_display):
    fin = make_financials(eps={"period_end": "2026-06-27", "report_date": None, "actual": actual, "estimate": estimate})
    facts = build_facts(fin, "demo")
    eps = facts["sections"]["eps"]
    assert eps["comparison"] == comparison == facts["headline"]["comparison"]
    assert eps["difference"]["display"] == diff_display
    assert facts["headline"]["label"] == f"EPS vs. analyst estimate: {comparison.capitalize()}"


def test_eps_missing_estimate():
    fin = make_financials(eps={"period_end": "2026-06-27", "report_date": None, "actual": 1.23, "estimate": None})
    facts = build_facts(fin, "demo")
    assert facts["sections"]["eps"]["comparison"] is None
    assert facts["headline"]["comparison"] is None
    assert facts["headline"]["label"] == "EPS vs. analyst estimate: Data not available"


def test_source_label_by_origin():
    assert build_facts(make_financials(), "demo")["sections"]["eps"]["source_label"] == \
        "Analyst average estimate (source: demo data)"
    assert build_facts(make_financials(), "live")["sections"]["eps"]["source_label"] == \
        "Analyst average estimate (source: Finnhub)"


def test_dividend_known_non_payer():
    fin = make_financials(dividend={"pays_dividend": False, "last_amount": None, "last_ex_date": None})
    div = build_facts(fin, "demo")["sections"]["dividend"]
    assert div["pays_dividend"] is False
    assert div["last_amount"]["display"] == "Data not available"
    assert div["last_ex_date"] is None


def test_dividend_unknown():
    fin = make_financials(dividend={"pays_dividend": None, "last_amount": None, "last_ex_date": None})
    assert build_facts(fin, "demo")["sections"]["dividend"]["pays_dividend"] is None


def test_missing_net_income():
    fin = make_financials()
    del fin["quarters"][0]["net_income"]
    assert build_facts(fin, "demo")["sections"]["profit"]["value"]["display"] == "Data not available"


def test_attach_explanations_never_changes_numbers():
    facts = build_facts(make_financials(), "demo")
    before = copy.deepcopy(facts)
    text = {k: f"{k} text" for k in ("headline", "revenue", "profit", "eps", "cash", "dividend")}
    out = attach_explanations(facts, {**text, "questions": ["a?", "b?", "c?"]}, "ai")
    assert facts == before  # input untouched
    assert out["headline"]["explain"] == "headline text"
    for key in ("revenue", "profit", "eps", "cash", "dividend"):
        assert out["sections"][key]["explain"] == f"{key} text"
        out["sections"][key]["explain"] = None
    out["headline"]["explain"] = None
    assert out["sections"] == before["sections"] and out["headline"] == before["headline"]
    assert out["questions_to_think_about"] == ["a?", "b?", "c?"] and out["explanation_source"] == "ai"
    assert "etf_explain" not in out


def test_route_missing_profile(client):
    resp = client.get("/api/stocks/AAPL/earnings?risk=medium")
    assert resp.status_code == 400 and resp.get_json()["error"]["code"] == "INVALID_PROFILE"


def test_route_etf(client):
    body = client.get("/api/stocks/VOO/earnings?age_range=25-34&risk=medium").get_json()
    data = body["data"]
    assert body["ok"] is True and body["source"] == "demo"
    assert data["is_etf"] is True and data["sections"] is None and data["period"] is None
    assert data["headline"] is None and data["etf_message"] == ETF_MESSAGE


def test_route_explanations_land_in_place(client, monkeypatch):
    plain = client.get("/api/stocks/AAPL/earnings?age_range=25-34&risk=medium").get_json()["data"]
    text = {k: f"{k} text" for k in ("headline", "revenue", "profit", "eps", "cash", "dividend")}
    monkeypatch.setattr(ai_service, "explain_earnings",
                        lambda facts, profile: ({**text, "questions": ["a?", "b?", "c?"]}, "ai"))
    body = client.get("/api/stocks/AAPL/earnings?age_range=25-34&risk=medium").get_json()
    data = body["data"]
    assert body["ok"] is True and data["explanation_source"] == "ai"
    assert data["headline"]["explain"] == "headline text"
    for key in ("revenue", "profit", "eps", "cash", "dividend"):
        assert data["sections"][key]["explain"] == f"{key} text"
        assert {k: v for k, v in data["sections"][key].items() if k != "explain"} == \
               {k: v for k, v in plain["sections"][key].items() if k != "explain"}


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "KO", "NVDA"])
def test_route_demo_stocks(client, ticker):
    body = client.get(f"/api/stocks/{ticker}/earnings?age_range=25-34&risk=medium").get_json()
    data = body["data"]
    assert body["ok"] is True and body["source"] == "demo"
    assert data["is_etf"] is False and "etf_explain" not in data
    assert set(data["sections"]) == {"revenue", "profit", "eps", "cash", "dividend"}
    assert data["sections"]["eps"]["source_label"] == "Analyst average estimate (source: demo data)"
