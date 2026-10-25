"""Brokerage Comparison Explorer (B1): data integrity, provenance, neutrality, filters, fee examples, staleness,
validation and the source checker. No network: the checker is tested with a fake fetch."""
import copy
import hashlib
import os
import re
import sys
from datetime import date, timedelta
from urllib.parse import urlparse

import pytest

from services import brokerages, documents
from services.errors import InvalidRequest

ROOT = os.path.join(os.path.dirname(__file__), "..")
TODAY = date(2026, 10, 25)
KINDS = {"firm_terms", "regulatory_record", "unknown"}
REGULATOR_HOSTS = ("files.brokercheck.finra.org", "brokercheck.finra.org")
TRACKING = re.compile(r"[?&](ref|utm_[a-z]+|aff|affiliate|affid|promo|campaign|cid|gclid|fbclid)=", re.IGNORECASE)
# App-written text must stay neutral: no rankings, safety labels or recommendations.
# Describing a firm's "recommendations" is allowed; the app itself recommending something is not.
NOT_NEUTRAL = re.compile(r"\b(best|safest|safe|top|recommend(s|ed|ing)?|winner|leading|cheapest|you should)\b",
                         re.IGNORECASE)


def all_firms():
    return list(brokerages.firms().values())


def fields():
    return brokerages.criteria()["fields"]


# ---- data integrity ----

def test_firms_in_alphabetical_order_and_e_trade_excluded_with_a_reason():
    assert [f["brand"] for f in all_firms()] == ["Charles Schwab", "Fidelity Investments", "Interactive Brokers", "Robinhood"]
    excluded = brokerages.criteria()["excluded"]
    assert excluded[0]["brand"] == "E*TRADE" and "legal entity" in excluded[0]["reason"]


def test_every_firm_covers_every_field_exactly_once():
    for firm in all_firms():
        got = [f["field"] for f in firm["facts"]]
        assert sorted(got) == sorted(fields()), firm["id"]


def test_criteria_cover_all_twelve_topics_and_every_field():
    c = brokerages.criteria()
    assert len(c["criteria"]) == 12
    used = [fid for cr in c["criteria"] for fid in cr["fields"]]
    assert sorted(used) == sorted(c["fields"])


def test_fact_values_match_their_field_type():
    for firm in all_firms():
        for f in firm["facts"]:
            assert f["kind"] in KINDS, (firm["id"], f["field"])
            date.fromisoformat(f["verified_on"])
            kind = fields()[f["field"]]["type"]
            if f["kind"] == "unknown":
                assert f["value"] is None and f["reason"].strip(), (firm["id"], f["field"])
            elif f.get("varies"):
                assert kind in ("money", "boolean") and f["value"] is None, (firm["id"], f["field"])
            elif kind == "money":
                assert isinstance(f["value"], int) and not isinstance(f["value"], bool) and f["value"] >= 0
            elif kind == "boolean":
                assert isinstance(f["value"], bool), (firm["id"], f["field"])
            else:
                assert f["value"] is None, (firm["id"], f["field"])


def fact_problems(firm, f):
    """Provenance rules every fact must meet, including facts the owner adds after a browser check."""
    if f["kind"] == "unknown":
        problems = ["source/quote on an unknown fact"] if "source" in f or "quote" in f else []
        if bool(f.get("check_source")) != bool(f.get("to_verify")):
            problems.append("check_source and to_verify must come together")
        if f.get("check_source") and f["check_source"] not in firm["sources"]:
            problems.append("check_source not in sources")
        return problems
    problems = []
    if f.get("method") not in brokerages.VERIFICATION:
        problems.append("missing or unknown verification method")
    if f.get("source") not in firm["sources"] or not firm["sources"][f["source"]].get("url"):
        problems.append("needs a source with a URL")
    if not f.get("location", "").strip() or not 0 < len(f.get("quote", "").split()) <= 40:
        problems.append("needs a location and a quote of at most 40 words")
    if f.get("method") == "owner_check" and not f.get("verified_by", "").strip():
        problems.append("owner checks must say who verified")
    if f["kind"] == "regulatory_record" and f.get("method") == "owner_check":
        problems.append("an owner check cannot be a regulatory record")
    return problems


def test_every_fact_meets_the_provenance_rules():
    for firm in all_firms():
        for f in firm["facts"]:
            assert fact_problems(firm, f) == [], (firm["id"], f["field"], fact_problems(firm, f))


OWNER_FACT = {"field": "option_contract_fee_cents", "kind": "firm_terms", "method": "owner_check", "verified_by": "App owner",
              "value": 65, "display": "$0.65 per contract.", "source": "pricing_guide", "location": "Pricing guide, options",
              "quote": "$0.65 per contract", "verified_on": "2026-10-26"}


def test_owner_verified_facts_are_accepted_and_labelled_as_not_certification():
    schwab = copy.deepcopy(brokerages.firms()["schwab"])
    assert fact_problems(schwab, OWNER_FACT) == []
    assert fact_problems(schwab, {**OWNER_FACT, "verified_by": ""}) == ["owner checks must say who verified"]
    assert "an owner check cannot be a regulatory record" in fact_problems(schwab, {**OWNER_FACT, "kind": "regulatory_record"})
    schwab["facts"] = [OWNER_FACT if f["field"] == OWNER_FACT["field"] else f for f in schwab["facts"]]
    original = brokerages._firms
    brokerages._firms = {**brokerages.firms(), "schwab": schwab}
    try:
        result = brokerages.compare(["schwab", "fidelity"], quantity=2, today=TODAY)
    finally:
        brokerages._firms = original
    cell = [r for cr in result["criteria"] for r in cr["rows"]
            if r["field"] == "option_contract_fee_cents"][0]["cells"]["schwab"]
    assert cell["verification"]["method"] == "owner_check" and cell["verification"]["by"] == "App owner"
    assert "Not a regulatory certification." in cell["verification"]["label"]
    assert cell["source"]["url"] == "https://www.schwab.com/pricing-guide" and cell["verified_on"] == "2026-10-26"
    assert result["fee_examples"][0]["results"]["schwab"] == {"cents": 130, "display": "$1.30"}


def test_every_source_is_dated_and_checkable():
    for firm in all_firms():
        for key, src in firm["sources"].items():
            date.fromisoformat(src["retrieved_on"])
            if src["effective"] is not None:
                date.fromisoformat(src["effective"])
            assert src["kind"] in ("regulatory_filing", "firm_pricing", "firm_page")
            assert src["check"] in ("hash", "quote", "manual")
            if src["check"] == "hash":
                assert re.fullmatch(r"[0-9a-f]{64}", src["sha256"])
            if src["kind"] == "regulatory_filing":
                assert src["effective"], (firm["id"], key)  # Form CRS effective dates are always shown


def test_each_firm_links_its_form_crs_and_a_pricing_source():
    for firm in all_firms():
        kinds = {s["kind"] for s in firm["sources"].values()}
        assert {"regulatory_filing", "firm_pricing"} <= kinds
        crs = [s for s in firm["sources"].values() if s["kind"] == "regulatory_filing"][0]
        assert crs["url"] == f"https://files.brokercheck.finra.org/crs_{firm['crd']}.pdf"
        assert firm["brokercheck_url"] == f"https://brokercheck.finra.org/firm/summary/{firm['crd']}"


def test_links_are_official_https_and_free_of_tracking():
    for firm in all_firms():
        urls = [firm["brokercheck_url"], *(s["url"] for s in firm["sources"].values())]
        for url in urls:
            host = urlparse(url).hostname
            assert url.startswith("https://") and not TRACKING.search(url), url
            assert host in REGULATOR_HOSTS or any(host == d or host.endswith("." + d) for d in firm["official_domains"]), url


def test_audit_trail_is_present_and_dated():
    for firm in all_firms():
        dates = [date.fromisoformat(a["date"]) for a in firm["audit"]]
        assert dates and dates == sorted(dates) and all(a["change"].strip() and a["by"].strip() for a in firm["audit"])


def test_promotions_are_never_shown_or_used():
    filters = brokerages.criteria()["filters"]
    assert all(fl["field"] != "promotions" for fl in filters)
    for firm in all_firms():
        promo = [f for f in firm["facts"] if f["field"] == "promotions"][0]
        assert promo["kind"] == "unknown" and promo["display"] == "Not shown"


def test_app_written_text_stays_neutral():
    c = brokerages.criteria()
    texts = [brokerages.NOTICE, brokerages.APP_INCENTIVES]
    texts += [cr["explanation"] for cr in c["criteria"]] + [fl["label"] for fl in c["filters"]]
    texts += [f["display"] for firm in all_firms() for f in firm["facts"]]
    texts += [f["reason"] for firm in all_firms() for f in firm["facts"] if f["kind"] == "unknown"]
    for text in texts:
        assert not NOT_NEUTRAL.search(text), text


def test_links_into_accounts_101_and_guides_resolve():
    with open(os.path.join(ROOT, "static", "js", "accounts.js"), encoding="utf-8") as f:
        accounts = f.read()
    for cr in brokerages.criteria()["criteria"]:
        for name in cr.get("accounts_101", []):
            assert f'["{name}",' in accounts, name
        if "guide" in cr:
            doc = documents.get_document(cr["guide"]["doc"])
            assert cr["guide"]["section"] in {s["id"] for s in doc["sections"]}, cr["id"]


# ---- comparison logic ----

def test_firm_order_is_alphabetical_whatever_the_request_order():
    a = brokerages.compare(["fidelity", "schwab"], today=TODAY)
    b = brokerages.compare(["schwab", "fidelity"], today=TODAY)
    assert [f["id"] for f in a["firms"]] == [f["id"] for f in b["firms"]] == ["schwab", "fidelity"]
    assert a == b


def test_filters_treat_unknown_as_unknown_never_as_no():
    result = brokerages.compare(["schwab", "fidelity"], filter_ids=["fractional", "no_minimum", "margin"], today=TODAY)
    got = {fl["id"]: fl["results"] for fl in result["filters"]}
    assert got["fractional"] == {"schwab": "unknown", "fidelity": "meets"}
    assert got["no_minimum"] == {"schwab": "meets", "fidelity": "meets"}
    assert result["filter_summary"]["schwab"] == {"meets": 1, "does_not_meet": 0, "varies": 0, "unknown": 2}


def test_plan_dependent_prices_are_never_counted_as_meeting_or_not():
    result = brokerages.compare(["ibkr", "robinhood"], filter_ids=["free_stock_etf_trades"], quantity=10, today=TODAY)
    assert result["filters"][0]["results"] == {"ibkr": "varies", "robinhood": "meets"}
    fee = result["fee_examples"][0]["results"]
    assert fee["ibkr"] is None and fee["robinhood"] == {"cents": 0, "display": "$0.00"}
    cell = [r for cr in result["criteria"] for r in cr["rows"]
            if r["field"] == "stock_etf_commission_cents"][0]["cells"]["ibkr"]
    assert cell["varies"] is True and "Depends on plan" in cell["display"]
    assert brokerages.match({"op": "eq", "value": 0}, {"kind": "firm_terms", "value": None, "varies": True}) == "varies"


def test_entity_notes_explain_affiliated_entities():
    by_id = {f["id"]: f for f in brokerages.overview()["firms"]}
    assert "Robinhood Securities, LLC" in by_id["robinhood"]["entity_note"]
    assert "Interactive Brokers LLC" in by_id["ibkr"]["entity_note"] and by_id["schwab"]["entity_note"] is None


def test_match_rule_outcomes():
    rule = {"op": "eq", "value": 0}
    assert brokerages.match(rule, {"kind": "firm_terms", "value": 0}) == "meets"
    assert brokerages.match(rule, {"kind": "firm_terms", "value": 5000}) == "does_not_meet"
    assert brokerages.match(rule, {"kind": "unknown", "value": None}) == "unknown"
    assert brokerages.match(rule, None) == "unknown"


@pytest.mark.parametrize("quantity, fidelity_cents, display", [(1, 65, "$0.65"), (10, 650, "$6.50"), (1000, 65000, "$650.00")])
def test_option_fee_example_in_whole_cents(quantity, fidelity_cents, display):
    fee = brokerages.compare(["schwab", "fidelity"], quantity=quantity, today=TODAY)["fee_examples"][0]
    assert fee["results"]["fidelity"] == {"cents": fidelity_cents, "display": display}
    assert fee["results"]["schwab"] is None  # unknown fee: no made-up example
    assert "exceptions" in fee["note"]


def test_cents_display():
    assert [brokerages.cents_display(c) for c in (0, 5, 65, 100, 123456)] == ["$0.00", "$0.05", "$0.65", "$1.00", "$1,234.56"]


def test_cells_show_source_dates_and_unknown_reasons():
    rows = {r["field"]: r for cr in brokerages.compare(["schwab", "fidelity"], today=TODAY)["criteria"] for r in cr["rows"]}
    known = rows["option_contract_fee_cents"]["cells"]["fidelity"]
    assert known["source"]["url"].startswith("https://www.fidelity.com/") and known["verified_on"] == "2026-10-25"
    assert known["quote"] and known["kind"] == "firm_terms" and known["verification"]["method"] == "source_check"
    crs = rows["account_minimum_cents"]["cells"]["schwab"]["source"]
    assert crs["kind"] == "regulatory_filing" and crs["effective"] == "2025-12-12"
    unknown = rows["option_contract_fee_cents"]["cells"]["schwab"]
    assert unknown["display"] == "Unknown" and unknown["reason"] and unknown["check_url"] == "https://www.schwab.com/pricing-guide"
    assert "per contract" in unknown["to_verify"]
    assert rows["regulatory_filing"]["cells"]["fidelity"]["kind"] == "regulatory_record"


def test_staleness_after_ninety_days():
    assert brokerages.age("2026-10-25", TODAY) == (0, False)
    assert brokerages.age("2026-07-27", TODAY) == (90, False)
    assert brokerages.age("2026-07-26", TODAY) == (91, True)
    later = brokerages.compare(["schwab", "fidelity"], today=TODAY + timedelta(days=91))
    cell = later["criteria"][0]["rows"][0]["cells"]["fidelity"]
    assert cell["stale"] is True and cell["age_days"] == 91 and cell["verified_on"] == "2026-10-25"


@pytest.mark.parametrize("kwargs, message", [
    ({"firm_ids": ["schwab"]}, "between 2"),
    ({"firm_ids": ["schwab", "schwab"]}, "only be chosen once"),
    ({"firm_ids": ["schwab", "etrade"]}, "Unknown firm"),
    ({"firm_ids": ["schwab", "fidelity"], "criteria_ids": ["vibes"]}, "Unknown criterion"),
    ({"firm_ids": ["schwab", "fidelity"], "filter_ids": ["cheapest"]}, "Unknown filter"),
    ({"firm_ids": ["schwab", "fidelity"], "quantity": 0}, "whole number"),
    ({"firm_ids": ["schwab", "fidelity"], "quantity": 1001}, "whole number"),
    ({"firm_ids": ["schwab", "fidelity"], "quantity": True}, "whole number"),
])
def test_invalid_selections_are_rejected(kwargs, message):
    with pytest.raises(InvalidRequest, match=message):
        brokerages.compare(**{"today": TODAY, **kwargs})


# ---- routes ----

def test_overview_route(client):
    data = client.get("/api/brokerages").get_json()["data"]
    assert [f["brand"] for f in data["firms"]] == ["Charles Schwab", "Fidelity Investments", "Interactive Brokers", "Robinhood"]
    assert set(data["verification_methods"]) == {"source_check", "owner_check"}
    assert data["excluded"][0]["brand"] == "E*TRADE" and data["stale_after_days"] == 90
    assert "does not rank" in data["notice"] and "no referral or affiliate" in data["app_incentives"]


def test_compare_route(client):
    body = client.get("/api/brokerages/compare?firms=fidelity,schwab&criteria=trading_costs&filters=fractional&quantity=3").get_json()
    assert body["ok"] is True
    data = body["data"]
    assert [c["id"] for c in data["criteria"]] == ["trading_costs"] and data["fee_examples"][0]["quantity"] == 3
    assert data["fee_examples"][0]["results"]["fidelity"]["display"] == "$1.95"


@pytest.mark.parametrize("query", ["firms=schwab", "firms=schwab,fidelity&quantity=abc", "firms=schwab,fidelity&quantity=-1",
                                   "firms=schwab,<script>", "firms=schwab,fidelity&criteria=nope", ""])
def test_compare_route_rejects_bad_input(client, query):
    resp = client.get(f"/api/brokerages/compare?{query}")
    assert resp.status_code == 400 and resp.get_json()["error"]["code"] == "INVALID_REQUEST"


def test_brokerage_routes_accept_no_user_data(client):
    rules = [r for r in client.application.url_map.iter_rules() if r.rule.startswith("/api/brokerages")]
    assert rules and all(r.methods <= {"GET", "HEAD", "OPTIONS"} for r in rules)
    assert client.post("/api/brokerages/compare", json={"ssn": "000-00-0000"}).status_code == 405


# ---- source checker (fake fetch, no network) ----

def checker():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import check_brokerage_sources
    return check_brokerage_sources


def test_checker_detects_changed_pdf_missing_quotes_and_manual_sources():
    firm = {"id": "demo", "sources": {
        "crs": {"url": "https://files.brokercheck.finra.org/crs_1.pdf", "check": "hash", "sha256": hashlib.sha256(b"v1").hexdigest()},
        "page": {"url": "https://demo.example/p", "check": "quote"},
        "site": {"url": "https://demo.example/blocked", "check": "manual"}},
        "facts": [
            {"field": "a", "kind": "firm_terms", "source": "crs", "quote": "x", "verified_on": "2026-10-25"},
            {"field": "b", "kind": "firm_terms", "source": "page", "quote": "Fee of $0.65 … per contract", "verified_on": "2026-10-25"},
            {"field": "c", "kind": "firm_terms", "source": "page", "quote": "No minimum", "verified_on": "2026-01-01"},
            {"field": "d", "kind": "unknown", "check_source": "site", "verified_on": "2026-10-25"}]}
    pages = {"https://files.brokercheck.finra.org/crs_1.pdf": b"v2",
             "https://demo.example/p": b"<p>Fee of $0.65</p><p>charged per\ncontract</p>"}
    rows = checker().check_firm(firm, pages.get, TODAY)
    statuses = {(s, d.split(":")[0]) for s, _, d in rows}
    assert ("CHANGED", "https") in statuses  # new PDF version
    assert ("OK", "b") in statuses and ("FAIL", "c") in statuses and ("STALE", "c") in statuses
    assert any(s == "MANUAL" and "d" in d for s, _, d in rows)
    assert checker().check_firm({**firm, "facts": []}, {}.get, TODAY)[0][0] == "UNREACHABLE"


def test_real_data_passes_the_checker_against_matching_sources():
    firm = copy.deepcopy(brokerages.firms()["fidelity"])
    page = " ".join(f["quote"] for f in firm["facts"] if f.get("source") in ("pricing", "fractional", "accounts")).encode()
    rows = checker().check_firm(firm, lambda url: page if "fidelity.com" in url else None, TODAY)
    assert not [r for r in rows if r[0] in ("FAIL", "STALE")]


def test_owner_checklist_lists_every_open_schwab_field_with_a_page_and_what_to_verify():
    items = checker().checklist(brokerages.firms()["schwab"])
    assert len(items) == 11
    for label, url, what in items:
        assert label and what.strip() and urlparse(url).hostname.endswith("schwab.com")


def test_checker_asks_for_periodic_rechecks_of_owner_verified_facts():
    firm = {"id": "demo", "sources": {"guide": {"url": "https://demo.example/guide", "check": "manual"}},
            "facts": [{**OWNER_FACT, "source": "guide"}]}
    rows = checker().check_firm(firm, {}.get, TODAY)
    assert any(s == "MANUAL" and "owner-checked 2026-10-26" in d for s, _, d in rows)
