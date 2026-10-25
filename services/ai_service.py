# Owner: Agent C. ONLY file that calls Claude. Python enforces the AI rules; the prompt alone is not trusted.
import json
import logging
import re

import anthropic

import config
from services import cache
from services.errors import AIUnavailable
from services.prompts import (
    BANNED_CHAT_PATTERNS,
    BANNED_EARNINGS_PATTERNS,
    CHAT_FALLBACK_ADVICE,
    CHAT_FALLBACK_NUMBERS,
    CHAT_SYSTEM_PROMPT,
    EARNINGS_SYSTEM_PROMPT,
    ETF_SYSTEM_PROMPT,
    FALLBACKS,
    STOCK_QUESTIONS,
)

log = logging.getLogger(__name__)

STOCK_KEYS = ("headline", "revenue", "profit", "eps", "cash", "dividend")
_DIGIT = re.compile(r"[0-9]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_NUMBER_IN_REPLY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?[TBMK]?|[+-]?\d[\d,]*(?:\.\d+)?%")
_CONTEXT_KEYS = {"ticker", "name", "display", "label", "title", "direction", "comparison", "explain",
                 "etf_message", "period_label", "source_label"}


def _call_claude(system, messages, max_tokens) -> str:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=config.AI_TIMEOUT_SECONDS)
    # Sonnet 5.5 thinks by default and thinking spends max_tokens; between_tools turns it off (valid at default effort).
    resp = client.messages.create(model=config.CLAUDE_MODEL, max_tokens=max_tokens, system=system, messages=messages,
                                  thinking={"type": "between_tools"})
    log.log(logging.WARNING if resp.stop_reason == "max_tokens" else logging.INFO,
            "claude stop_reason=%s output_tokens=%s max_tokens=%s",
            resp.stop_reason, getattr(resp.usage, "output_tokens", None), max_tokens)
    return "".join(block.text for block in resp.content if block.type == "text")


# ---- earnings explanations ----

def _earnings_payload(facts, profile):
    """AI_RULES §5.1: directions and comparisons only. Never a number."""
    if facts.get("is_etf"):
        return {"is_etf": True, "profile": profile}
    s = facts["sections"]
    comparison = facts["headline"]["comparison"]
    return {
        "is_etf": False,
        "profile": profile,
        "headline": {"available": comparison is not None, "comparison": comparison},
        "revenue": {"available": s["revenue"]["value"]["value"] is not None, "direction": s["revenue"]["direction"]},
        "profit": {"available": s["profit"]["value"]["value"] is not None, "direction": s["profit"]["direction"]},
        "eps": {"available": s["eps"]["actual"]["value"] is not None, "comparison": s["eps"]["comparison"]},
        "cash": {"available": s["cash"]["value"]["value"] is not None},
        "dividend": {"available": s["dividend"]["pays_dividend"] is not None,
                     "pays_dividend": s["dividend"]["pays_dividend"]},
    }


def _fallback(key, payload):
    item = payload.get(key, {})
    if key == "headline":
        return FALLBACKS["headline"].get(item.get("comparison"))
    if key in ("revenue", "profit"):
        return FALLBACKS[key].get(item.get("direction"), FALLBACKS[key]["flat"])
    if key == "dividend":
        return FALLBACKS["dividend"]["pays" if item.get("pays_dividend") else "does_not_pay"]
    return FALLBACKS[key]["any"]


def _keys(payload):
    return ("etf",) if payload["is_etf"] else STOCK_KEYS


def _available(key, payload):
    return key == "etf" or payload[key]["available"]


def _fixed_questions(payload):
    return list(FALLBACKS["questions"]["etf"] if payload["is_etf"] else STOCK_QUESTIONS[payload["profile"]["risk"]])


def _full_fallback(payload):
    out = {k: _fallback(k, payload) if _available(k, payload) else None for k in _keys(payload)}
    out["questions"] = _fixed_questions(payload)
    return out, "fallback"


def _text_problem(value):
    """V2-V5 for one field. Returns the failed check id, or None if the text is clean."""
    if not isinstance(value, str) or not value.strip():
        return "V2 missing"
    if _DIGIT.search(value):
        return "V3 digit"
    if BANNED_EARNINGS_PATTERNS.search(value):
        return "V4 banned term"
    sentences = [s for s in _SENTENCE_SPLIT.split(value.strip()) if s]
    if len(sentences) > 3 or any(len(s.split()) > 30 for s in sentences):
        return "V5 length"
    return None


def _parse_first_json_object(text):
    start = text.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _validate(raw_text, payload, ticker):
    parsed = _parse_first_json_object(raw_text)
    if parsed is None:
        log.warning("V1 invalid JSON ticker=%s", ticker)
        return _full_fallback(payload)

    out, from_ai = {}, False
    for key in _keys(payload):
        if not _available(key, payload):
            out[key] = None  # V6: always null, whatever Claude wrote
            continue
        problem = _text_problem(parsed.get(key))
        if problem:
            log.warning("%s in field=%s ticker=%s", problem, key, ticker)
            out[key] = _fallback(key, payload)
        else:
            out[key] = parsed[key].strip()
            from_ai = True

    if not payload["is_etf"]:
        out["questions"] = _fixed_questions(payload)  # stocks: approved set for profile.risk, never Claude's
        return out, "ai" if from_ai else "fallback"
    questions = parsed.get("questions")
    ok_questions = (
        isinstance(questions, list) and len(questions) == 3
        and all(isinstance(q, str) and q.strip().endswith("?") and not _DIGIT.search(q)
                and not BANNED_EARNINGS_PATTERNS.search(q) for q in questions)
    )
    if ok_questions:
        out["questions"] = [q.strip() for q in questions]
        from_ai = True
    else:
        log.warning("V7 questions failed ticker=%s", ticker)
        out["questions"] = _fixed_questions(payload)
    return out, "ai" if from_ai else "fallback"


def explain_earnings(facts: dict, profile: dict) -> tuple[dict, str]:
    ticker = facts.get("ticker")
    try:
        payload = _earnings_payload(facts, profile)
    except Exception:
        log.exception("could not build earnings payload ticker=%s", ticker)
        if facts.get("is_etf"):
            return _full_fallback({"is_etf": True})
        return {**{k: None for k in STOCK_KEYS}, "questions": list(STOCK_QUESTIONS[profile["risk"]])}, "fallback"
    if not config.ANTHROPIC_API_KEY:
        return _full_fallback(payload)

    period = "etf" if payload["is_etf"] else (facts.get("period") or {}).get("period_end")
    key = f"ai:earnings:{ticker}:{period}:{profile['age_range']}:{profile['risk']}"
    hit = cache.get(key)
    if hit:
        return hit
    try:
        system = ETF_SYSTEM_PROMPT if payload["is_etf"] else EARNINGS_SYSTEM_PROMPT
        raw = _call_claude(system, [{"role": "user", "content": json.dumps(payload)}], config.AI_MAX_TOKENS_EARNINGS)
        result = _validate(raw, payload, ticker)
    except Exception:
        log.exception("explain_earnings failed ticker=%s, using fallback", ticker)
        return _full_fallback(payload)
    if result[1] == "ai":  # a short outage must not pin fallback text for 24h
        cache.set(key, result, config.TTL_AI)
    return result


# ---- chat ----

def _reduce(value):
    """Keep only display strings, labels, titles, directions, comparisons and explain texts (AI_RULES §6.1)."""
    if isinstance(value, dict):
        if isinstance(value.get("display"), str) and set(value) <= {"value", "display"}:
            return value["display"]
        out = {}
        for k, v in value.items():
            if k in _CONTEXT_KEYS and isinstance(v, str):
                out[k] = v
            elif isinstance(v, (dict, list)):
                reduced = _reduce(v)
                if reduced:
                    out[k] = reduced
        return out
    if isinstance(value, list):
        return [r for r in (_reduce(v) for v in value) if r]
    return None


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def reduce_context(context_facts):
    if not isinstance(context_facts, dict):
        return {}
    return _reduce({k: context_facts.get(k) for k in ("ticker", "snapshot", "earnings")})


def chat(message: str, history: list, profile: dict, context_facts: dict | None) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise AIUnavailable()
    context = reduce_context(context_facts)
    system = CHAT_SYSTEM_PROMPT.format(profile=json.dumps(profile), context=json.dumps(context) if context else "none")

    turns = [{"role": h["role"], "content": h["content"]} for h in history
             if isinstance(h, dict) and h.get("role") in ("user", "assistant")
             and isinstance(h.get("content"), str) and h["content"].strip()][-config.CHAT_HISTORY_LIMIT:]
    while turns and turns[0]["role"] != "user":  # the API expects the conversation to open with a user turn
        turns.pop(0)
    try:
        reply = _call_claude(system, turns + [{"role": "user", "content": message}], config.AI_MAX_TOKENS_CHAT)
    except Exception:
        log.exception("chat call failed")
        raise AIUnavailable() from None
    if not reply.strip():
        raise AIUnavailable()

    if BANNED_CHAT_PATTERNS.search(reply):  # C3 first: advice matters more than a number
        log.warning("C3 banned advice in chat reply")
        return CHAT_FALLBACK_ADVICE
    # C2: each $ amount / % value must exactly match one shown in the app or typed by the user
    allowed = {n for s in [*_strings(context), message] for n in _NUMBER_IN_REPLY.findall(s)}
    unverified = [n for n in _NUMBER_IN_REPLY.findall(reply) if n not in allowed]
    if unverified:
        log.warning("C2 unverified numbers in chat reply: %s", unverified)
        return CHAT_FALLBACK_NUMBERS
    return reply.strip()
