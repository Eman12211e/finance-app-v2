"""Builds the earnings facts object (API_CONTRACT §3.3). Pure Python. No AI. Missing input -> null output."""
import copy
from datetime import date

from services.formatting import date_display, field, money_large, money_per_share, pct_change

ETF_MESSAGE = "ETFs hold many companies. They do not report earnings. Look at the fund's holdings and fees instead."
SECTION_KEYS = ("revenue", "profit", "eps", "cash", "dividend")


def _prior_year(quarters):
    current = date.fromisoformat(quarters[0]["period_end"])
    for q in quarters[1:]:
        if 350 <= (current - date.fromisoformat(q["period_end"])).days <= 380:
            return q
    return None  # never substitute a different quarter


def _change(current, prior):
    if current is None or prior is None or prior == 0:
        return None
    return (current - prior) / abs(prior) * 100


def _direction(change):
    if change is None:
        return None
    return "up" if change > 0.5 else "down" if change < -0.5 else "flat"


def _growth_section(title, key, current_q, prior_q):
    value = current_q.get(key) if current_q else None
    prior = prior_q.get(key) if prior_q else None
    change = _change(value, prior)
    return {
        "title": title,
        "value": field(value, money_large),
        "prior_year_value": field(prior, money_large),
        "change_percent": field(change, pct_change),
        "direction": _direction(change),
        "explain": None,
    }


def _eps_section(eps, source_origin):
    eps = eps or {}
    actual, estimate = eps.get("actual"), eps.get("estimate")
    diff = round(actual - estimate, 2) if actual is not None and estimate is not None else None
    if diff is None:
        comparison = None
    else:
        comparison = "above" if diff >= 0.01 else "below" if diff <= -0.01 else "equal"
    period_end = eps.get("period_end")
    return {
        "title": "Earnings per share vs. analyst estimate",
        "period_label": f"Quarter ended {date_display(period_end)}" if period_end else None,
        "report_date": eps.get("report_date"),
        "actual": field(actual, money_per_share),
        "estimate": field(estimate, money_per_share),
        "difference": field(diff, money_per_share),
        "comparison": comparison,
        "source_label": "Analyst average estimate (source: "
                        + ("Finnhub)" if source_origin == "live" else "demo data)"),
        "explain": None,
    }


def _dividend_section(div):
    div = div or {}
    pays = div.get("pays_dividend")
    return {
        "title": "Dividend",
        "pays_dividend": pays,
        "last_amount": field(div.get("last_amount") if pays else None, money_per_share),
        "last_ex_date": div.get("last_ex_date") if pays else None,
        "explain": None,
    }


def build_facts(financials, source_origin):
    if financials.get("is_etf"):
        return {
            "ticker": financials["ticker"],
            "is_etf": True,
            "etf_message": ETF_MESSAGE,
            "etf_explain": None,
            "period": None,
            "headline": None,
            "sections": None,
            "questions_to_think_about": [],
            "explanation_source": None,
        }

    quarters = financials.get("quarters") or []
    current = quarters[0] if quarters else None
    prior = _prior_year(quarters) if quarters else None
    eps = _eps_section(financials.get("eps"), source_origin)
    comparison = eps["comparison"]
    return {
        "ticker": financials["ticker"],
        "is_etf": False,
        "etf_message": None,
        "period": {"label": f"Quarter ended {date_display(current['period_end'])}",
                   "period_end": current["period_end"]} if current else None,
        "headline": {
            "comparison": comparison,
            "label": "EPS vs. analyst estimate: " + (comparison.capitalize() if comparison else "Data not available"),
            "explain": None,
        },
        "sections": {
            "revenue": _growth_section("Revenue", "revenue", current, prior),
            "profit": _growth_section("Profit (net income)", "net_income", current, prior),
            "eps": eps,
            "cash": {
                "title": "Cash and cash equivalents",
                "value": field(current.get("cash_and_equivalents") if current else None, money_large),
                "explain": None,
            },
            "dividend": _dividend_section(financials.get("dividend")),
        },
        "questions_to_think_about": [],
        "explanation_source": None,
    }


def attach_explanations(data, explanations, explanation_source):
    """Fills explain fields and questions only. Never touches a number."""
    out = copy.deepcopy(data)
    if out["is_etf"]:
        out["etf_explain"] = explanations.get("etf")
    else:
        out["headline"]["explain"] = explanations.get("headline")
        for key in SECTION_KEYS:
            out["sections"][key]["explain"] = explanations.get(key)
    out["questions_to_think_about"] = list(explanations.get("questions") or [])
    out["explanation_source"] = explanation_source
    return out
