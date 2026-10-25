"""Brokerage Comparison Explorer: dated, source-backed facts in data/brokerages/*.json.
Neutral by design: firms are always listed alphabetically, filters never rank, unknown is never treated as "no",
and promotions are not used. No user data is accepted beyond which firms, criteria and filters to show."""
import json
import os
from datetime import date

from services.errors import InvalidRequest
from services.formatting import cents_display

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
FIRMS_DIR = os.path.join(DATA_DIR, "brokerages")
STALE_AFTER_DAYS = 90
MAX_FIRMS = 4
MAX_QUANTITY = 1000
NOTICE = ("This compares published facts. It does not rank firms or tell you which one to choose. "
          "The right fit depends on your own needs.")
APP_INCENTIVES = "This app has no referral or affiliate relationship with any brokerage firm."
# How a fact was checked. An owner check is a person reading the official source; it is not regulatory certification.
VERIFICATION = {
    "source_check": "Matched word for word against the official source by the app's source check.",
    "owner_check": "Checked by the app owner in a browser against the official source. Not a regulatory certification.",
}
_criteria = None
_firms = None


def criteria():
    global _criteria
    if _criteria is None:
        with open(os.path.join(DATA_DIR, "brokerage_criteria.json"), encoding="utf-8") as f:
            _criteria = json.load(f)
    return _criteria


def firms():
    """All firms, keyed by id, in alphabetical order of brand."""
    global _firms
    if _firms is None:
        loaded = []
        for name in os.listdir(FIRMS_DIR):
            if name.endswith(".json"):
                with open(os.path.join(FIRMS_DIR, name), encoding="utf-8") as f:
                    loaded.append(json.load(f))
        _firms = {d["id"]: d for d in sorted(loaded, key=lambda d: d["brand"].lower())}
    return _firms


def age(verified_on, today):
    days = (today - date.fromisoformat(verified_on)).days
    return days, days > STALE_AFTER_DAYS


def match(rule, fact):
    """'meets' | 'does_not_meet' | 'varies' | 'unknown'. Missing, unknown or plan-dependent facts never count as not meeting."""
    if fact is not None and fact.get("varies"):
        return "varies"
    if fact is None or fact["kind"] == "unknown" or fact["value"] is None:
        return "unknown"
    if rule["op"] == "eq":
        return "meets" if fact["value"] == rule["value"] else "does_not_meet"
    raise ValueError(f"unsupported filter op {rule['op']}")


def fee_example(fact, quantity):
    """Total of a per-unit fee in cents, or None when the fee is unknown or depends on the plan."""
    if fact is None or fact["kind"] == "unknown" or fact.get("varies") or not isinstance(fact["value"], int):
        return None
    total = fact["value"] * quantity
    return {"cents": total, "display": cents_display(total)}


def _facts(firm):
    return {f["field"]: f for f in firm["facts"]}


def _cell(firm, fact, today):
    days, stale = age(fact["verified_on"], today)
    cell = {"kind": fact["kind"], "display": fact["display"], "value": fact["value"], "varies": bool(fact.get("varies")),
            "verified_on": fact["verified_on"], "age_days": days, "stale": stale}
    if fact["kind"] == "unknown":
        cell["reason"] = fact["reason"]
        check = firm["sources"].get(fact.get("check_source"))
        cell["check_url"] = check["url"] if check else None
        cell["to_verify"] = fact.get("to_verify")
    else:
        cell["verification"] = {"method": fact["method"], "label": VERIFICATION[fact["method"]],
                                "by": fact.get("verified_by")}
        src = firm["sources"][fact["source"]]
        cell.update(location=fact["location"], quote=fact["quote"],
                    source={k: src[k] for k in ("publisher", "title", "url", "kind", "effective", "retrieved_on")})
    return cell


def _pick(requested, known, what, default):
    if requested is None:
        return list(default)
    if len(set(requested)) != len(requested):
        raise InvalidRequest(f"Each {what} can only be chosen once.")
    unknown = [r for r in requested if r not in known]
    if unknown:
        raise InvalidRequest(f"Unknown {what}: {', '.join(unknown)}.")
    return requested


def overview():
    c = criteria()
    return {
        "firms": [{k: f[k] for k in ("id", "brand", "legal_entity", "crd", "brokercheck_url")}
                  | {"entity_note": f.get("entity_note")} for f in firms().values()],
        "criteria": [{**{k: v for k, v in cr.items() if k != "fields"},
                      "fields": [{"id": fid, **c["fields"][fid]} for fid in cr["fields"]]} for cr in c["criteria"]],
        "filters": [{k: fl[k] for k in ("id", "label")} for fl in c["filters"]],
        "fee_examples": [{"id": k, **v} for k, v in c["fee_examples"].items()],
        "excluded": c["excluded"], "notice": NOTICE, "app_incentives": APP_INCENTIVES,
        "stale_after_days": STALE_AFTER_DAYS, "verification_methods": VERIFICATION,
    }


def compare(firm_ids, criteria_ids=None, filter_ids=None, quantity=1, today=None):
    today = today or date.today()
    c = criteria()
    all_firms = firms()
    if firm_ids is None or not 2 <= len(firm_ids) <= MAX_FIRMS:
        raise InvalidRequest(f"Please choose between 2 and {MAX_FIRMS} firms to compare.")
    _pick(firm_ids, all_firms, "firm", [])
    chosen = [f for fid, f in all_firms.items() if fid in firm_ids]  # alphabetical, whatever order was requested
    by_criterion = {cr["id"]: cr for cr in c["criteria"]}
    crit = _pick(criteria_ids, by_criterion, "criterion", by_criterion)
    by_filter = {fl["id"]: fl for fl in c["filters"]}
    filt = _pick(filter_ids, by_filter, "filter", [])
    if not isinstance(quantity, int) or isinstance(quantity, bool) or not 1 <= quantity <= MAX_QUANTITY:
        raise InvalidRequest(f"The example quantity must be a whole number from 1 to {MAX_QUANTITY}.")

    facts = {f["id"]: _facts(f) for f in chosen}
    rows = []
    for cid in crit:
        cr = by_criterion[cid]
        rows.append({**{k: v for k, v in cr.items() if k != "fields"},
                     "rows": [{"field": fid, "label": c["fields"][fid]["label"],
                               "cells": {f["id"]: _cell(f, facts[f["id"]][fid], today) for f in chosen}}
                              for fid in cr["fields"]]})
    filters = [{"id": fid, "label": by_filter[fid]["label"],
                "results": {f["id"]: match(by_filter[fid], facts[f["id"]].get(by_filter[fid]["field"])) for f in chosen}}
               for fid in filt]
    summary = {f["id"]: {r: sum(fl["results"][f["id"]] == r for fl in filters)
                         for r in ("meets", "does_not_meet", "varies", "unknown")}
               for f in chosen}
    fees = [{"id": k, "label": v["label"], "unit": v["unit"], "note": v["note"], "quantity": quantity,
             "results": {f["id"]: fee_example(facts[f["id"]].get(v["field"]), quantity) for f in chosen}}
            for k, v in c["fee_examples"].items()]
    return {"firms": [{k: f[k] for k in ("id", "brand", "legal_entity", "crd", "brokercheck_url")}
                      | {"entity_note": f.get("entity_note")} for f in chosen],
            "criteria": rows, "filters": filters, "filter_summary": summary, "fee_examples": fees,
            "notice": NOTICE, "app_incentives": APP_INCENTIVES, "excluded": c["excluded"],
            "stale_after_days": STALE_AFTER_DAYS, "today": today.isoformat()}
