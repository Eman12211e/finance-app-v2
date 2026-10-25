"""AI Strategy Comparison Lab: one evidence pack, one prompt, one schema and one rule set for every model.
Python checks every output; the prompt alone is not trusted. Models are never ranked, and mock output is
labelled SIMULATED all the way to the screen."""
import hashlib
import json

import config
from services import earnings_service, llm_providers, market_data
from services.errors import BudgetExceeded, InvalidRequest, LiveInferenceDisabled
from services.prompts import LAB_BANNED_PATTERNS, LAB_SCENARIOS, LAB_SYSTEM_PROMPT, NUMBER_PATTERN

SIMULATED_LABEL = "SIMULATED — NOT REAL MODEL OUTPUT"
SIMULATED_NOTICE = ("These panels come from deterministic test stand-ins, not from Qwen, Kimi, DeepSeek, GPT-OSS, GLM "
                    "or Claude. Their checks test this app's validators. They are not model scores, rankings or "
                    "investment results.")
WITHHELD = "[Withheld: this text broke the no-advice rule.]"

# Evaluation criteria. "auto" ones are computed on every output; the rest need a benchmark or human raters.
CRITERIA = [
    {"key": "schema_valid", "name": "Instruction following: output format", "how": "auto"},
    {"key": "citations_valid", "name": "Evidence grounding: citations point to real evidence", "how": "auto"},
    {"key": "numbers_traceable", "name": "Numerical accuracy: every number appears in the cited evidence", "how": "auto"},
    {"key": "advice_violations", "name": "Instruction following: no advice or predictions", "how": "auto"},
    {"key": "unsupported_claims", "name": "Evidence grounding: claims without a citation", "how": "auto"},
    {"key": "states_uncertainty", "name": "Uncertainty: names what the evidence does not show", "how": "auto"},
    {"key": "latency_ms", "name": "Latency", "how": "auto (live only)"},
    {"key": "cost_usd", "name": "Cost", "how": "auto (live only)"},
    {"key": "factual_accuracy", "name": "Factual accuracy of interpretations", "how": "benchmark with human raters"},
    {"key": "risk_identification", "name": "Risk identification", "how": "benchmark with human raters"},
    {"key": "consistency", "name": "Consistency across repeated runs", "how": "benchmark (repeated runs)"},
]


# ---- evidence ----

def build_evidence(ticker):
    snap, _, _ = market_data.get_snapshot(ticker)
    fin, source, as_of = market_data.get_financials(ticker)
    facts = earnings_service.build_facts(fin, "demo" if source == "demo" else "live")
    rows = [("Share price", snap["price"]), ("Daily price change", snap["change_percent"]),
            ("Market capitalization", snap["market_cap"]), ("Dividend yield", snap["dividend_yield"])]
    if snap["is_etf"]:
        rows.append(("Expense ratio (yearly fund cost)", snap["expense_ratio"]))
    else:
        s = facts["sections"]
        pays = s["dividend"]["pays_dividend"]
        rows += [
            ("Revenue, latest quarter", s["revenue"]["value"]),
            ("Revenue, same quarter last year", s["revenue"]["prior_year_value"]),
            ("Revenue change vs. same quarter last year", s["revenue"]["change_percent"]),
            ("Net income, latest quarter", s["profit"]["value"]),
            ("Net income change vs. same quarter last year", s["profit"]["change_percent"]),
            ("Cash and cash equivalents", s["cash"]["value"]),
            ("Earnings per share, actual", s["eps"]["actual"]),
            ("Earnings per share, analyst estimate", s["eps"]["estimate"]),
            ("Pays a dividend", {"value": pays, "display": {True: "Yes", False: "No"}.get(pays)}),
        ]
    present = [(label, f["display"]) for label, f in rows if f["value"] is not None]
    return {
        "ticker": snap["ticker"], "name": snap.get("name"), "is_etf": snap["is_etf"],
        "period_label": facts["period"]["label"] if facts.get("period") else None,
        "source": source, "as_of": as_of,
        "items": [{"id": f"E{i}", "label": label, "value": value} for i, (label, value) in enumerate(present, 1)],
        "not_available": [label for label, f in rows if f["value"] is None],
    }


def build_prompt(evidence, scenario_key):
    scenario = {"key": scenario_key, **LAB_SCENARIOS[scenario_key]}
    user = json.dumps({"scenario": scenario, "company": evidence["name"], "period": evidence["period_label"],
                       "as_of": evidence["as_of"],
                       "evidence": [{k: e[k] for k in ("id", "label", "value")} for e in evidence["items"]],
                       "not_in_evidence": evidence["not_available"]})
    return LAB_SYSTEM_PROMPT, user, hashlib.sha256((LAB_SYSTEM_PROMPT + "\n" + user).encode()).hexdigest()


# ---- validation (same checks for every model) ----

def _strings(value):
    return [v.strip() for v in value if isinstance(v, str) and v.strip()] if isinstance(value, list) else []


def _ids(value):
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _check(text, evidence_ids, by_id, violations):
    """One claim or risk: redacts advice language, flags unknown ids, uncited text and untraceable numbers."""
    issues = []
    if LAB_BANNED_PATTERNS.search(text):
        violations.append({"type": "advice_language", "detail": "Advice or prediction language was withheld."})
        return {"text": WITHHELD, "evidence_ids": evidence_ids, "issues": ["advice_language"]}
    unknown = [i for i in evidence_ids if i not in by_id]
    if unknown:
        issues.append("unknown_citation")
        violations.append({"type": "unknown_citation", "detail": f"Cites evidence that does not exist: {', '.join(unknown)}."})
    known = [i for i in evidence_ids if i in by_id]
    if not known:
        issues.append("unsupported")
    allowed = {n for i in known for n in NUMBER_PATTERN.findall(by_id[i]["value"])}
    bad = [n for n in NUMBER_PATTERN.findall(text) if n not in allowed]
    if bad:
        issues.append("number_not_in_evidence")
        violations.append({"type": "number_not_in_evidence",
                           "detail": f"Numbers not found in the cited evidence: {', '.join(bad)}."})
    return {"text": text, "evidence_ids": evidence_ids, "issues": issues}


def _parse(text):
    if not isinstance(text, str):
        return None
    start = text.find("{")
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:]) if start >= 0 else (None, 0)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def validate_output(raw_text, evidence):
    """Returns the checked panel content. Never trusts the model's numbers, citations or wording."""
    by_id = {e["id"]: e for e in evidence["items"]}
    parsed = _parse(raw_text)
    if parsed is None:
        return {"status": "invalid_output", "analysis": None, "claims": [], "risks": [], "assumptions": [],
                "uncertainties": [], "unsupported_claims": [], "violations": [
                    {"type": "invalid_output", "detail": "The output was not valid JSON, so nothing from it is shown."}],
                "checks": {"schema_valid": False, "citations_valid": None, "numbers_traceable": None,
                           "advice_violations": 0, "unsupported_claims": 0, "states_uncertainty": False}}

    violations = []
    schema_valid = (isinstance(parsed.get("analysis"), str) and all(
        isinstance(parsed.get(k), list) for k in ("claims", "risks", "assumptions", "uncertainties")))
    analysis = parsed.get("analysis") if isinstance(parsed.get("analysis"), str) else ""
    if LAB_BANNED_PATTERNS.search(analysis):
        violations.append({"type": "advice_language", "detail": "Advice or prediction language was withheld."})
        analysis = WITHHELD
    else:
        all_numbers = {n for e in evidence["items"] for n in NUMBER_PATTERN.findall(e["value"])}
        bad = [n for n in NUMBER_PATTERN.findall(analysis) if n not in all_numbers]
        if bad:
            violations.append({"type": "number_not_in_evidence",
                               "detail": f"Analysis numbers not found in the evidence: {', '.join(bad)}."})

    claims = []
    for c in parsed.get("claims") if isinstance(parsed.get("claims"), list) else []:
        if not (isinstance(c, dict) and isinstance(c.get("text"), str) and c["text"].strip()):
            schema_valid = False
            continue
        checked = _check(c["text"].strip(), _ids(c.get("evidence_ids")), by_id, violations)
        checked["stance"] = c.get("stance") if c.get("stance") in ("supports", "weakens", "neutral") else "neutral"
        claims.append(checked)
    risks = [_check(r["text"].strip(), _ids(r.get("evidence_ids")), by_id, violations)
             for r in (parsed.get("risks") if isinstance(parsed.get("risks"), list) else [])
             if isinstance(r, dict) and isinstance(r.get("text"), str) and r["text"].strip()]

    cited = [i for item in claims + risks for i in item["evidence_ids"]]
    numbered = [item for item in claims + risks if NUMBER_PATTERN.search(item["text"])]
    uncertainties = _strings(parsed.get("uncertainties"))
    return {
        "status": "ok", "analysis": analysis, "claims": claims, "risks": risks,
        "assumptions": _strings(parsed.get("assumptions")), "uncertainties": uncertainties,
        "unsupported_claims": [c["text"] for c in claims if "unsupported" in c["issues"]],
        "violations": violations,
        "checks": {
            "schema_valid": schema_valid,
            "citations_valid": {"passed": sum(i in by_id for i in cited), "total": len(cited)},
            "numbers_traceable": {"passed": sum("number_not_in_evidence" not in i["issues"] for i in numbered),
                                  "total": len(numbered)},
            "advice_violations": sum(v["type"] == "advice_language" for v in violations),
            "unsupported_claims": sum("unsupported" in c["issues"] for c in claims),
            "states_uncertainty": bool(uncertainties),
        },
    }


# ---- cross-model comparison ----

def find_disagreements(panels, evidence):
    """Same evidence id, opposite stance (supports vs. weakens) from different models."""
    labels = {e["id"]: e["label"] for e in evidence["items"]}
    out = []
    for eid in labels:
        sides = {"supports": [], "weakens": []}
        for p in panels:
            stances = {c["stance"] for c in p["claims"] if eid in c["evidence_ids"] and "advice_language" not in c["issues"]}
            for s in sides:
                if s in stances:
                    sides[s].append(p["model"]["label"])
        if sides["supports"] and sides["weakens"]:
            out.append({"evidence_id": eid, "label": labels[eid], **sides})
    return out


def coverage(panels, evidence):
    return [{"evidence_id": e["id"], "label": e["label"],
             "cited_by": [p["model"]["label"] for p in panels
                          if any(e["id"] in i["evidence_ids"] for i in p["claims"] + p["risks"])]}
            for e in evidence["items"]]


def public_model(m):
    return {k: m[k] for k in ("key", "label", "adapter", "model_id", "provider", "license", "status")}


def compare(ticker, scenario_key, model_keys=None, live=False):
    if scenario_key not in LAB_SCENARIOS:
        raise InvalidRequest("Please choose a conservative, balanced or aggressive scenario.")
    keys = model_keys or [m["key"] for m in llm_providers.registry()["models"]]
    models = [llm_providers.get_model(k) for k in keys]
    evidence = build_evidence(ticker)
    if not evidence["items"]:
        raise InvalidRequest(f"There is no evidence available for {ticker}.")
    system, user, prompt_hash = build_prompt(evidence, scenario_key)
    max_tokens = config.LAB_MAX_TOKENS
    worst = sum(llm_providers.worst_case_usd(m, system, user, max_tokens) for m in models)

    if live:  # all-or-nothing: never a silent mix of live and simulated panels
        blocked = {m["label"]: r for m in models if (r := llm_providers.live_block_reasons(m))}
        if blocked:
            raise LiveInferenceDisabled(" ".join(f"{name}: {' '.join(r)}" for name, r in blocked.items()))
        if llm_providers.spent_today_usd() + worst > llm_providers.daily_budget_usd():
            raise BudgetExceeded()

    panels = []
    # shortcut: models run one after another, use a thread pool if live latency matters
    for m in models:
        result = llm_providers.complete(m, system, user, max_tokens, live=live)
        if result["error"]:
            checked = {**validate_output(None, evidence), "status": "unavailable"}
            checked["violations"] = []
        else:
            checked = validate_output(result["text"], evidence)
        panel = {"model": public_model(m), "inference": result["inference"], "simulated": not live,
                 "prompt_sha256": prompt_hash, **checked, "error": result["error"],
                 "latency_ms": result["latency_ms"], "input_tokens": result["input_tokens"],
                 "output_tokens": result["output_tokens"], "cost_usd": result["cost_usd"],
                 "truncated": result["truncated"]}
        if not live:
            panel["simulated_label"] = SIMULATED_LABEL
            panel["test_case"] = llm_providers.mock_test_case(m["key"], scenario_key)[1]
        panels.append(panel)

    disagreements = find_disagreements(panels, evidence)
    for p in panels:
        p["disagreements"] = [d for d in disagreements if p["model"]["label"] in d["supports"] + d["weakens"]]
    return {
        "mode": "live" if live else "simulated",
        "simulated_label": None if live else SIMULATED_LABEL,
        "notice": None if live else SIMULATED_NOTICE,
        "scenario": {"key": scenario_key, **LAB_SCENARIOS[scenario_key]},
        "evidence": evidence,
        "prompt_sha256": prompt_hash,
        "max_tokens": max_tokens,
        "panels": panels,
        "disagreements": disagreements,
        "coverage": coverage(panels, evidence),
        "criteria": CRITERIA,
        "estimated_live_max_cost_usd": f"{worst:.6f}",
    }
