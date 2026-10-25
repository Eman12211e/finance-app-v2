# ONLY file that sends Lab prompts to a model. It knows nothing about finance: text in, text and usage out.
# Live calls pass every activation gate and a budget reservation first; the mock never touches the network.
import json
import logging
import threading
import time
from datetime import date
from decimal import Decimal, InvalidOperation

import anthropic
import requests

import config
from services.errors import BudgetExceeded, InvalidRequest, LiveInferenceDisabled
from services.prompts import LAB_SCENARIOS

log = logging.getLogger(__name__)
MILLION = Decimal(1_000_000)
_registry = None
_ledger_lock = threading.Lock()


# ---- model registry (data/lab_models.json) ----

def registry():
    global _registry
    if _registry is None:
        with open(config.LAB_MODELS_PATH, encoding="utf-8") as f:
            _registry = json.load(f)
    return _registry


def get_model(key):
    model = next((m for m in registry()["models"] if m["key"] == key), None)
    if model is None:
        raise InvalidRequest(f"Unknown model: {key}.")
    return model


# ---- activation gates and budget ----

def daily_budget_usd():
    try:
        return max(Decimal(config.LAB_DAILY_BUDGET_USD), Decimal(0))
    except InvalidOperation:
        return Decimal(0)


def live_block_reasons(model):
    """Every reason a live call to this model is refused. Empty list = allowed."""
    reasons = []
    if config.ZERO_COST_MODE:
        reasons.append("Zero-cost development mode is on (ZERO_COST_MODE).")
    if not config.LAB_LIVE_ENABLED:
        reasons.append("Live inference is not activated (LAB_LIVE_ENABLED).")
    if daily_budget_usd() <= 0:
        reasons.append("The spending limit is $0 (LAB_DAILY_BUDGET_USD).")
    key_name = "HF_TOKEN" if model["adapter"] == "hf" else "ANTHROPIC_API_KEY"
    if not getattr(config, key_name):
        reasons.append(f"No {key_name} is set.")
    if model.get("status") != "confirmed":
        reasons.append("The model id and provider are provisional (data/lab_models.json).")
    return reasons


def estimate_tokens(text):
    return len(text) // 4 + 1  # shortcut: ~4 characters per token, use provider token counts once live runs are approved


def cost_usd(model, input_tokens, output_tokens):
    return (Decimal(input_tokens) * Decimal(model["price_in_per_m"])
            + Decimal(output_tokens) * Decimal(model["price_out_per_m"])) / MILLION


def worst_case_usd(model, system, user, max_tokens):
    return cost_usd(model, estimate_tokens(system + user), max_tokens)


def _read_ledger():
    try:
        with open(config.LAB_SPEND_LEDGER, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    # A corrupt ledger raises: spend can then not be proven, so no live call goes out.


def spent_today_usd():
    try:
        return Decimal(_read_ledger().get(date.today().isoformat(), "0"))
    except (ValueError, InvalidOperation):
        return daily_budget_usd()  # unreadable ledger counts as budget used up


def _add_spend(amount, limit=None):
    """Adds to today's spend. With a limit, refuses (and records nothing) if the total would pass it."""
    with _ledger_lock:
        today = date.today().isoformat()
        try:
            ledger = _read_ledger()
            current = Decimal(ledger.get(today, "0"))
        except (ValueError, InvalidOperation):
            raise BudgetExceeded("The spend ledger could not be read, so no live call was sent.") from None
        if limit is not None and current + amount > limit:
            raise BudgetExceeded()
        ledger[today] = str(current + amount)
        with open(config.LAB_SPEND_LEDGER, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2)


def _reserve(amount):
    """Record the worst case before the call, so a crash or a parallel request can never overspend."""
    _add_spend(amount, limit=daily_budget_usd())


# ---- providers ----

def _call_hf(model, system, user, max_tokens):
    # Hugging Face router, OpenAI-compatible. "<model>:<provider>" pins the provider so prices match the registry.
    resp = requests.post(
        f"{config.HF_ROUTER_URL}/chat/completions",
        headers={"Authorization": f"Bearer {config.HF_TOKEN}"},
        json={"model": f"{model['model_id']}:{model['provider']}",
              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
              "max_tokens": max_tokens, "temperature": 0, "response_format": {"type": "json_object"}},
        timeout=config.LAB_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    body = resp.json()
    choice, usage = body["choices"][0], body.get("usage") or {}
    return (choice["message"].get("content") or "", usage.get("prompt_tokens"), usage.get("completion_tokens"),
            choice.get("finish_reason") == "length")


def _call_anthropic(model, system, user, max_tokens):
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=config.LAB_TIMEOUT_SECONDS)
    # Same call shape V1 verified live for Sonnet 5.5 (services/ai_service.py). between_tools is Sonnet 5.5 only.
    resp = client.messages.create(model=model["model_id"], max_tokens=max_tokens, system=system,
                                  messages=[{"role": "user", "content": user}], thinking={"type": "between_tools"})
    if resp.stop_reason == "refusal":
        raise RuntimeError("model declined the request")
    text = "".join(block.text for block in resp.content if block.type == "text")
    return text, resp.usage.input_tokens, resp.usage.output_tokens, resp.stop_reason == "max_tokens"


# Deterministic stand-ins. Each test case exercises one validator; cases rotate across models by scenario,
# so no model is ever shown as consistently better or worse. They say nothing about the real models.
MOCK_TEST_CASES = [
    ("clean", "Follows every rule."),
    ("number_not_in_evidence", "Writes a number that is not in the evidence."),
    ("unknown_citation", "Cites an evidence id that does not exist."),
    ("advice_language", "Uses buy/sell advice language."),
    ("uncited_claim", "Makes a claim with no citation."),
    ("malformed_output", "Returns output that is not valid JSON."),
]
_STANCES = ("supports", "weakens", "neutral")


def mock_test_case(model_key, scenario_key):
    model_index = [m["key"] for m in registry()["models"]].index(model_key)
    return MOCK_TEST_CASES[(model_index + list(LAB_SCENARIOS).index(scenario_key)) % len(MOCK_TEST_CASES)]


def _mock_text(model, user):
    payload = json.loads(user)
    case, _ = mock_test_case(model["key"], payload["scenario"]["key"])
    if case == "malformed_output":
        return "Simulated malformed output {not json"
    items = payload["evidence"]
    offset = [m["key"] for m in registry()["models"]].index(model["key"])
    picked = [items[(offset + i) % len(items)] for i in range(min(3, len(items)))]
    claims = [{"text": f"Simulated claim: {e['label']} is {e['value']}.", "evidence_ids": [e["id"]],
               "stance": _STANCES[(2 * offset + i) % 3]} for i, e in enumerate(picked)]
    first = picked[0]["id"] if picked else "E1"
    extra = {
        "number_not_in_evidence": {"text": "Simulated claim: a value of $123.45 appears here.", "evidence_ids": [first],
                                   "stance": "neutral"},
        "unknown_citation": {"text": "Simulated claim citing evidence that does not exist.", "evidence_ids": ["E99"],
                             "stance": "neutral"},
        "advice_language": {"text": "Simulated rule break: you should buy this now.", "evidence_ids": [first],
                            "stance": "supports"},
        "uncited_claim": {"text": "Simulated claim with no supporting evidence.", "evidence_ids": [], "stance": "supports"},
    }.get(case)
    return json.dumps({
        "analysis": f"Simulated analysis under the {payload['scenario']['label']} lens, citing {len(picked)} of "
                    f"{len(items)} evidence items.",
        "claims": claims + ([extra] if extra else []),
        "risks": [{"text": "Simulated risk: the evidence covers few periods, so it may not show a trend.",
                   "evidence_ids": [first]}],
        "assumptions": ["Simulated assumption: the evidence values are accurate as of the stated date."],
        "uncertainties": ["Simulated uncertainty: the evidence does not explain why any value changed."],
    })


def complete(model, system, user, max_tokens, live=False):
    """One model call. live=False always uses the mock. Returns text plus usage; never raises for provider errors."""
    out = {"model_key": model["key"], "inference": "live" if live else "mock", "text": None, "latency_ms": None,
           "input_tokens": None, "output_tokens": None, "cost_usd": "0", "truncated": False, "error": None}
    if not live:
        out["text"] = _mock_text(model, user)
        return out
    reasons = live_block_reasons(model)
    if reasons:
        raise LiveInferenceDisabled(" ".join(reasons))
    worst = worst_case_usd(model, system, user, max_tokens)
    _reserve(worst)
    start = time.monotonic()
    try:
        call = _call_hf if model["adapter"] == "hf" else _call_anthropic
        text, in_tokens, out_tokens, truncated = call(model, system, user, max_tokens)
    except Exception as exc:  # the reservation stays: a failed call may still have been billed
        log.warning("lab call failed model=%s error=%s", model["key"], type(exc).__name__)
        out["error"] = "The provider did not return a usable response."
        return out
    actual = cost_usd(model, in_tokens, out_tokens) if in_tokens is not None and out_tokens is not None else worst
    _add_spend(actual - worst)
    out.update(text=text, latency_ms=round((time.monotonic() - start) * 1000), input_tokens=in_tokens,
               output_tokens=out_tokens, cost_usd=str(actual), truncated=truncated)
    return out
