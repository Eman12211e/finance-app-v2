"""Check that quoted passages in data/documents/*.json still match their sources word for word.
Free: plain GETs of public pages, no keys, no AI. Checks official and firm passages (split at "…") and quoted
phrases inside summaries. PDF sources need a manual check because extracting PDF text needs a dependency.
Whitespace is ignored when comparing, since source pages wrap text differently."""
import html
import os
import re
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services import documents  # noqa: E402

USER_AGENT = "FinanceAppV2 source check (educational, non-commercial)"  # sec.gov and others require a declared agent


def page_text(raw):
    raw = re.sub(r"(?s)<(script|style).*?</\1>", " ", raw)
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def segments(section):
    if section["origin"] in ("official", "firm"):
        return [p.strip() for p in section["passage"].split("…") if p.strip()]
    if section["origin"] == "summary":
        return re.findall(r'"([^"]{20,})"', section["passage"])
    return []


def check(doc, texts):
    """texts maps source key -> source text (or None if unavailable). Returns (status, section id, detail) rows."""
    rows = []
    for s in doc["sections"]:
        for seg in segments(s):
            text = texts.get(s["source"])
            if text is None:
                rows.append(("MANUAL", s["id"], f"check against {doc['sources'][s['source']]['url']}"))
            elif re.sub(r"\s+", "", seg) in re.sub(r"\s+", "", text):
                rows.append(("OK", s["id"], "matches source"))
            else:
                rows.append(("FAIL", s["id"], f"not found: {seg[:80]}"))
    return rows


def fetch(url):
    if not url or url.lower().endswith(".pdf"):
        return None
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    return page_text(resp.text) if resp.status_code == 200 else None


def main():
    failed = 0
    for listed in documents.list_documents():
        doc = documents.get_document(listed["id"])
        texts = {key: fetch(src["url"]) for key, src in doc["sources"].items()}
        for status, section_id, detail in check(doc, texts):
            failed += status == "FAIL"
            print(f"{status:<7} {doc['id']:<22} {section_id:<26} {detail}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
