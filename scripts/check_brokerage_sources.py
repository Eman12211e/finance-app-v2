"""Check brokerage facts against their sources. Free: plain GETs of public pages, no keys, no AI.
- "hash" sources (PDF filings): a changed SHA-256 means a new version; re-verify every fact from it.
- "quote" sources (HTML): each fact's quote must still appear on the page (whitespace ignored).
- "manual" sources (sites that refuse automated requests): listed for a person to check in a browser.
Also lists facts verified more than 90 days ago. Never edits the data: a person updates it and adds an audit entry."""
import hashlib
import os
import re
import sys
from datetime import date

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services import brokerages  # noqa: E402
from check_document_sources import USER_AGENT, page_text  # noqa: E402  (same scripts folder)


def quote_segments(quote):
    return [s.strip() for s in quote.split("…") if s.strip()]


def check_firm(firm, fetch, today):
    """fetch(url) -> bytes or None. Returns (status, firm id, detail) rows."""
    rows = []
    for key, src in firm["sources"].items():
        facts = [f for f in firm["facts"] if f.get("source") == key]
        waiting = [f["field"] for f in firm["facts"] if f.get("check_source") == key]
        if src["check"] == "manual":
            rows.append(("MANUAL", firm["id"], f"{src['url']}: verify by hand ({', '.join(waiting) or 'no open fields'})"))
            continue
        body = fetch(src["url"])
        if body is None:
            rows.append(("UNREACHABLE", firm["id"], src["url"]))
        elif src["check"] == "hash":
            same = hashlib.sha256(body).hexdigest() == src["sha256"]
            rows.append(("OK" if same else "CHANGED", firm["id"],
                         f"{src['url']}: " + ("unchanged" if same else f"new version; re-verify {len(facts)} facts")))
        else:
            text = re.sub(r"\s+", "", page_text(body.decode("utf-8", errors="ignore")))
            for f in facts:
                found = all(re.sub(r"\s+", "", seg) in text for seg in quote_segments(f["quote"]))
                rows.append(("OK" if found else "FAIL", firm["id"], f"{f['field']}: " + ("quote found" if found else "quote not found")))
    for f in firm["facts"]:
        days, stale = brokerages.age(f["verified_on"], today)
        if stale:
            rows.append(("STALE", firm["id"], f"{f['field']}: verified {days} days ago"))
    return rows


def fetch(url):
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    return resp.content if resp.status_code == 200 else None


def main():
    problems = 0
    for firm in brokerages.firms().values():
        for status, firm_id, detail in check_firm(firm, fetch, date.today()):
            problems += status in ("FAIL", "CHANGED", "UNREACHABLE", "STALE")
            print(f"{status:<12} {firm_id:<10} {detail}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
