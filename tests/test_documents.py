"""Understand Before You Sign: content structure, provenance, wording, privacy and routes. No network."""
import os
import re
import sys
from datetime import date

import pytest

from services import documents
from services.prompts import LAB_BANNED_PATTERNS

ROOT = os.path.join(os.path.dirname(__file__), "..")
DOC_FIELDS = {"id", "title", "summary", "card_blurb", "when_you_see_it", "sources", "sections"}
SECTION_FIELDS = {"id", "heading", "origin", "source", "location", "passage", "plain_english", "why_it_matters",
                  "tags", "look_for", "questions"}
TAGS = {"fees", "risks", "rights", "disclosures", "personal_information"}
LICENSE_FOR_ORIGIN = {"official": "public_domain", "firm": "quoted_with_attribution", "summary": "summarized",
                      "example": "app_written"}
OFFICIAL_HOSTS = ("https://www.sec.gov/", "https://www.irs.gov/", "https://www.govinfo.gov/", "https://www.investor.gov/")
SUMMARY_HOSTS = ("https://www.finra.org/", "https://brokercheck.finra.org/", "https://www.sipc.org/")
# App-written text must not advise, predict, push a signature or claim to be legal/tax advice.
EXTRA_BANNED = re.compile(r"\b(you should|sign (it|this|the agreement)|go ahead and|legal advice|tax advice"
                          r"|safe|best(?! interest))\b", re.IGNORECASE)


def all_docs():
    return [documents.get_document(d["id"]) for d in documents.list_documents()]


def all_sections():
    return [(d, s) for d in all_docs() for s in d["sections"]]


# ---- structure ----

def test_five_documents_one_file_each_in_order():
    files = sorted(f[:-5] for f in os.listdir(documents.DOCS_DIR) if f.endswith(".json"))
    assert files == sorted(documents.ORDER) and len(files) == 5
    assert [d["id"] for d in documents.list_documents()] == list(documents.ORDER)


def test_required_fields_and_unique_ids():
    ids = []
    for d in all_docs():
        assert set(d) == DOC_FIELDS, d["id"]
        for s in d["sections"]:
            assert SECTION_FIELDS <= set(s) <= SECTION_FIELDS | {"accounts_101"}, s["id"]
            assert all(isinstance(s[k], str) and s[k].strip() for k in SECTION_FIELDS - {"tags", "look_for", "questions"})
            ids.append(s["id"])
    assert len(ids) == len(set(ids))


def test_tags_questions_and_look_for():
    used = set()
    for _, s in all_sections():
        assert s["tags"] and set(s["tags"]) <= TAGS, s["id"]
        used |= set(s["tags"])
        assert s["look_for"] and s["questions"], s["id"]
        assert all(q.strip().endswith("?") for q in s["questions"]), s["id"]
    assert used == TAGS  # fees, risks, rights, disclosures and personal information are all covered


# ---- provenance ----

def test_every_source_has_a_version_and_retrieval_date():
    for d in all_docs():
        for key, src in d["sources"].items():
            assert src["publisher"] and src["title"] and src["version"], (d["id"], key)
            date.fromisoformat(src["retrieved_on"])
            assert src["license"] in LICENSE_FOR_ORIGIN.values(), (d["id"], key)


def test_origin_matches_source_license_and_host():
    for d, s in all_sections():
        src = d["sources"][s["source"]]
        assert src["license"] == LICENSE_FOR_ORIGIN[s["origin"]], s["id"]
        if s["origin"] == "official":
            assert src["url"].startswith(OFFICIAL_HOSTS), s["id"]
        elif s["origin"] == "firm":
            assert src["url"].startswith("https://reports.adviserinfo.sec.gov/crs/"), s["id"]  # SEC-hosted firm filing
        elif s["origin"] == "summary":
            assert src["url"].startswith(SUMMARY_HOSTS) and s["passage"].startswith("Summary: "), s["id"]
        else:
            assert src["url"] is None and "not a real firm" in src["title"], s["id"]


def test_finra_and_firm_material_is_quoted_only_briefly():
    for d, s in all_sections():
        if s["origin"] == "summary":
            quotes = re.findall(r'"([^"]+)"', s["passage"])
            long_quotes = [q for q in quotes if len(q.split()) > 4]
            assert len(long_quotes) <= 1 and all(len(q.split()) <= 25 for q in quotes), s["id"]
        if s["origin"] == "firm":
            assert len(s["passage"].split()) <= 40, s["id"]


def test_elided_passages_keep_real_segments_on_both_sides():
    for _, s in all_sections():
        if "…" in s["passage"]:
            assert s["origin"] in ("official", "firm")
            assert all(p.strip() for p in s["passage"].split("…")), s["id"]


def test_form_crs_pairs_sec_requirements_with_one_real_firm():
    crs = documents.get_document("form-crs")
    origins = [s["origin"] for s in crs["sections"]]
    assert {"official", "firm"} == set(origins) and origins.count("firm") >= 2
    assert {s["source"] for s in crs["sections"] if s["origin"] == "firm"} == {"schwab_crs"}


# ---- wording and safety ----

def test_app_written_text_gives_no_advice_or_signing_push():
    for _, s in all_sections():
        texts = [s["plain_english"], s["why_it_matters"], *s["look_for"], *s["questions"]]
        if s["origin"] == "example":
            texts.append(s["passage"])  # fictional clauses are ours too
        for text in texts:
            assert not LAB_BANNED_PATTERNS.search(text) and not EXTRA_BANNED.search(text), (s["id"], text)


def test_w9_is_text_only_and_warns_against_typing_numbers_here():
    w9 = documents.get_document("form-w9")
    assert "Never type your number into this app." in w9["summary"]
    assert any(s["id"] == "w9-phishing" and "passwords" in s["passage"] for s in w9["sections"])


def test_accounts_101_links_point_to_real_entries():
    with open(os.path.join(ROOT, "static", "js", "accounts.js"), encoding="utf-8") as f:
        accounts = f.read()
    linked = {s["accounts_101"] for _, s in all_sections() if "accounts_101" in s}
    assert {"Margin brokerage", "Cash brokerage"} <= linked
    for name in linked:
        assert f'["{name}",' in accounts, name


# ---- routes ----

def test_list_route(client):
    body = client.get("/api/documents").get_json()
    assert body["ok"] is True
    docs = body["data"]["documents"]
    assert [d["id"] for d in docs] == list(documents.ORDER)
    assert all(d["section_count"] > 0 and d["origins"] for d in docs)


def test_detail_route(client):
    body = client.get("/api/documents/form-w9").get_json()
    assert body["ok"] is True and body["data"]["id"] == "form-w9" and body["data"]["sections"]


@pytest.mark.parametrize("doc_id, status, code", [("no-such-doc", 404, "DATA_NOT_AVAILABLE"),
                                                   ("BAD_ID", 400, "INVALID_REQUEST")])
def test_detail_errors(client, doc_id, status, code):
    resp = client.get(f"/api/documents/{doc_id}")
    assert resp.status_code == status and resp.get_json()["error"]["code"] == code


def test_document_routes_accept_no_user_data(client):
    rules = [r for r in client.application.url_map.iter_rules() if r.rule.startswith("/api/documents")]
    assert rules and all(r.methods <= {"GET", "HEAD", "OPTIONS"} for r in rules)
    assert client.post("/api/documents/form-w9", json={"ssn": "000-00-0000"}).status_code == 405


# ---- source checker (fixture text only) ----

def test_source_checker_matches_ignoring_whitespace_and_flags_changes():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import check_document_sources as checker
    doc = {"sources": {"a": {"url": "https://www.irs.gov/x.pdf"}, "b": {"url": "https://www.finra.org/r"}},
           "sections": [
               {"id": "s1", "origin": "official", "source": "a", "passage": "Give form to the requester. … Do not send."},
               {"id": "s2", "origin": "summary", "source": "b", "passage": 'Summary: it says "You can lose more funds than you deposit".'},
               {"id": "s3", "origin": "example", "source": "a", "passage": "Fictional."},
           ]}
    rows = checker.check(doc, {"a": "Give form  to the\nrequester. Then: Do not send.", "b": "You can lose less."})
    assert rows == [("OK", "s1", "matches source"), ("OK", "s1", "matches source"),
                    ("FAIL", "s2", "not found: You can lose more funds than you deposit")]
    assert checker.check(doc, {})[0][0] == "MANUAL"


# ---- interface (static checks; the page itself is checked in a real browser before release) ----

def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def test_page_has_sign_tab_and_scripts_in_order(client):
    html = client.get("/").get_data(as_text=True)
    assert 'data-tab="sign"' in html and 'id="sign-root"' in html
    assert html.index("/static/js/accounts.js") < html.index("/static/js/sign.js") < html.index("/static/js/app.js")


def test_sign_js_collects_and_stores_nothing():
    js = read("static", "js", "sign.js")
    for banned in ("innerHTML", "fetch(", "localStorage", "sessionStorage", "document.cookie", "XMLHttpRequest",
                   "textarea", '"text"', '"file"', '"password"', "FormData", "postDocument"):
        assert banned not in js, banned
    assert re.findall(r'\.type = "(\w+)"', js) and set(re.findall(r'box\.type = "(\w+)"', js)) == {"checkbox"}
    assert "Nothing you select is saved or sent." in js


SAFETY = [
    "Your Safety Comes First",
    "Before signing any financial document, take time to understand its terms, fees, potential risks, and your rights. "
    "Always verify that you're dealing with a legitimate financial institution and review any agreement carefully "
    "before providing personal information or signing.",
    "Never enter your Social Security number, identification documents, or account passwords into this educational guide.",
    "Educational information only. Not legal, tax, or investment advice.",
]
# Neither promise nor permanently rule out signing, submission or account opening.
SIGNING_CLAIMS = re.compile(r"never signs|does not sign|doesn't sign|submit forms|opens? (an )?accounts? for you"
                            r"|sign (online|here|now|electronically)|e-?sign|electronic signature|submit (your|this|the)",
                            re.IGNORECASE)


def js_strings(js):
    """The page text as written in sign.js, with string concatenations joined."""
    return re.sub(r'"\s*\+\s*"', "", js)


def test_safety_panel_has_the_exact_approved_copy():
    text = js_strings(read("static", "js", "sign.js"))
    for line in SAFETY:
        assert line in text, line


def test_no_claim_that_signing_or_account_opening_is_supported():
    texts = [js_strings(read("static", "js", "sign.js")), read("templates", "index.html")]
    texts += [read("data", "documents", f"{d}.json") for d in documents.ORDER]
    for text in texts:
        assert not SIGNING_CLAIMS.search(text), SIGNING_CLAIMS.search(text).group(0)
    assert "This app does not sign documents" not in texts[0]


def test_intro_wording():
    text = js_strings(read("static", "js", "sign.js"))
    assert ("Before opening an investment account, understand the documents you're agreeing to, the risks involved, "
            "and the rights you may be giving up.") in text
    assert "Read key passages from account documents next to plain-English explanations" not in text


def test_form_crs_is_named_and_explained_for_beginners():
    crs = documents.get_document("form-crs")
    assert crs["title"] == "Form CRS (Customer Relationship Summary)"
    assert crs["summary"] == ("A short disclosure document that explains a financial firm's services, fees, conflicts "
                              "of interest, and disciplinary history. It helps you understand important details before "
                              "choosing a firm.")
    assert documents.list_documents()[0]["title"] == crs["title"]  # first visible mention: the first document card


def test_every_card_says_what_it_is_and_why_to_review_it():
    for d in documents.list_documents():
        assert "Review it to" in d["card_blurb"] and len(d["card_blurb"].split()) <= 30, d["id"]


def test_sign_js_labels_every_origin_and_links_accounts_101():
    js = read("static", "js", "sign.js")
    for label in ("Official text", "Firm disclosure", "Summary", "Fictional example"):
        assert label in js
    assert "window.Accounts.open(s.accounts_101)" in js
    assert "function open(entryName)" in read("static", "js", "accounts.js")


def test_checklist_prints_alone_and_layout_stacks_on_phones():
    css = read("static", "css", "features.css")
    assert "@media print" in css and "body.print-checklist #sign-checklist" in css
    assert ".sign-top, .sign-layout, .sign-row { grid-template-columns: minmax(0, 1fr); }" in css
    assert ".sign-top { display: grid; gap: var(--s-4); grid-template-columns: minmax(0, 1fr) 360px;" in css


def test_alert_toast_only_shows_on_explore():
    assert "document.body.dataset.tab = tab;" in read("static", "js", "app.js")
    assert 'body[data-tab]:not([data-tab="explore"]) .fe-toast { display: none; }' in read("static", "css", "features.css")


def test_tabs_are_owned_by_app_js():
    assert "showTab" in read("static", "js", "app.js")
    assert '".tab"' not in read("static", "js", "lab.js") and '".tab"' not in read("static", "js", "sign.js")
