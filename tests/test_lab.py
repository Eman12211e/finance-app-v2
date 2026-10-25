"""AI Strategy Comparison Lab: six models, simulated by default, validators, activation gates and budget.
No test makes a real call: conftest blocks requests and anthropic, and live-path tests install fakes."""
import copy
import json
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal

import pytest
import requests

import config
from services import llm_providers, strategy_lab
from services.errors import BudgetExceeded, LiveInferenceDisabled

ROOT = os.path.join(os.path.dirname(__file__), "..")
LABEL = "SIMULATED — NOT REAL MODEL OUTPUT"
KEYS = ["qwen", "kimi", "deepseek", "gpt-oss", "glm", "claude"]


def compare(client, **body):
    return client.post("/api/lab/compare", json={"ticker": "KO", "scenario": "balanced", **body})


@pytest.fixture
def live_ready(monkeypatch, tmp_path):
    """Every activation gate open and every model confirmed. Network stays blocked until a test installs a fake."""
    monkeypatch.setattr(config, "ZERO_COST_MODE", False)
    monkeypatch.setattr(config, "LAB_LIVE_ENABLED", True)
    monkeypatch.setattr(config, "LAB_DAILY_BUDGET_USD", "1.00")
    monkeypatch.setattr(config, "HF_TOKEN", "hf-test-not-real")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test-not-real")
    monkeypatch.setattr(config, "LAB_SPEND_LEDGER", str(tmp_path / "spend.json"))
    reg = copy.deepcopy(llm_providers.registry())
    for m in reg["models"]:
        m["status"] = "confirmed"
    monkeypatch.setattr(llm_providers, "_registry", reg)
    return tmp_path / "spend.json"


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


def fake_hf(monkeypatch, content, sent):
    def post(url, headers, json, timeout):
        sent.append({"url": url, "headers": headers, "json": json})
        return FakeResponse({"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                             "usage": {"prompt_tokens": 1000, "completion_tokens": 500}})
    monkeypatch.setattr(requests, "post", post)


def ledger_today(path):
    with open(path, encoding="utf-8") as f:
        return Decimal(json.load(f)[date.today().isoformat()])


# ---- zero-cost mode ----

@pytest.mark.parametrize("zero_cost, expect_keys", [(None, False), ("1", False), ("0", True)])
def test_zero_cost_mode_blanks_every_paid_key(zero_cost, expect_keys):
    env = {**os.environ, "ANTHROPIC_API_KEY": "a", "FINNHUB_API_KEY": "f", "FMP_API_KEY": "m", "HF_TOKEN": "h",
           "DATA_MODE": "live", "WARM_CACHE": "1"}
    env.pop("ZERO_COST_MODE", None)
    if zero_cost is not None:
        env["ZERO_COST_MODE"] = zero_cost
    out = subprocess.run([sys.executable, "-c", "import config; print(config.ANTHROPIC_API_KEY, config.FINNHUB_API_KEY,"
                          " config.FMP_API_KEY, config.HF_TOKEN, config.DATA_MODE, config.WARM_CACHE)"],
                         cwd=ROOT, env=env, capture_output=True, text=True, check=True).stdout.split()
    assert out == (["a", "f", "m", "h", "live", "True"] if expect_keys else ["demo", "False"])


def test_health_reports_zero_cost_mode(client):
    assert client.get("/api/health").get_json()["data"]["zero_cost_mode"] is True


# ---- registry and config ----

def test_registry_has_six_models_with_prices_and_no_secrets():
    reg = llm_providers.registry()
    assert reg["verified_on"] and [m["key"] for m in reg["models"]] == KEYS
    for m in reg["models"]:
        assert m["adapter"] == ("anthropic" if m["key"] == "claude" else "hf")
        assert m["status"] == "provisional" and m["model_id"] and m["provider"] and m["license"]
        assert Decimal(m["price_in_per_m"]) > 0 and Decimal(m["price_out_per_m"]) > 0
        assert not any("key" in k.lower() or "token" == k.lower() for k in m if k != "key")


def test_config_endpoint_shows_simulated_only(client):
    data = client.get("/api/lab/config").get_json()["data"]
    assert data["zero_cost_mode"] is True and data["live_available"] is False
    assert data["daily_budget_usd"] == "0" and data["simulated_label"] == LABEL
    assert [s["key"] for s in data["scenarios"]] == ["conservative", "balanced", "aggressive"]
    assert [m["key"] for m in data["models"]] == KEYS
    for m in data["models"]:
        assert any("Zero-cost" in r for r in m["live_blocked_reasons"])
        assert any("$0" in r for r in m["live_blocked_reasons"])


# ---- simulated comparison ----

@pytest.mark.parametrize("ticker", ["KO", "VOO"])
@pytest.mark.parametrize("scenario", ["conservative", "balanced", "aggressive"])
def test_six_panels_all_labelled_simulated_with_identical_prompt(client, ticker, scenario):
    body = compare(client, ticker=ticker, scenario=scenario).get_json()
    assert body["ok"] is True and body["source"] == "demo"
    data = body["data"]
    assert data["mode"] == "simulated" and data["simulated_label"] == LABEL and "not model scores" in data["notice"]
    assert [p["model"]["key"] for p in data["panels"]] == KEYS
    for p in data["panels"]:
        assert p["simulated"] is True and p["inference"] == "mock" and p["simulated_label"] == LABEL
        assert p["prompt_sha256"] == data["prompt_sha256"]
        assert p["cost_usd"] == "0" and p["latency_ms"] is None and p["test_case"]
        assert p["checks"]["simulated"] is True
    ids = [e["id"] for e in data["evidence"]["items"]]
    assert len(ids) == len(set(ids)) >= 3


def test_simulated_comparison_is_deterministic(client):
    assert compare(client).get_json() == compare(client).get_json()


def test_each_simulated_test_case_trips_its_validator(client):
    panels = compare(client).get_json()["data"]["panels"]
    by_case = {p["test_case"]: p for p in panels}
    assert len(by_case) == 6
    clean = by_case["Follows every rule."]
    assert clean["status"] == "ok" and clean["violations"] == [] and clean["unsupported_claims"] == []
    assert clean["checks"]["citations_valid"]["passed"] == clean["checks"]["citations_valid"]["total"]
    assert {v["type"] for v in by_case["Writes a number that is not in the evidence."]["violations"]} == {
        "number_not_in_evidence"}
    assert "unknown_citation" in {v["type"] for v in by_case["Cites an evidence id that does not exist."]["violations"]}
    advice = by_case["Uses buy/sell advice language."]
    assert advice["checks"]["advice_violations"] == 1 and "you should buy" not in json.dumps(advice).lower()
    assert by_case["Makes a claim with no citation."]["checks"]["unsupported_claims"] == 1
    bad = by_case["Returns output that is not valid JSON."]
    assert bad["status"] == "invalid_output" and bad["claims"] == [] and bad["analysis"] is None


def test_test_cases_rotate_so_no_model_is_always_flawed(client):
    seen = {k: set() for k in KEYS}
    for scenario in ("conservative", "balanced", "aggressive"):
        for p in compare(client, scenario=scenario).get_json()["data"]["panels"]:
            seen[p["model"]["key"]].add(p["test_case"])
    assert all(len(cases) == 3 for cases in seen.values())


def test_disagreements_appear_on_the_panels_involved(client):
    data = compare(client, ticker="VOO", scenario="conservative").get_json()["data"]
    assert data["disagreements"]
    for d in data["disagreements"]:
        assert d["supports"] and d["weakens"] and not set(d["supports"]) & set(d["weakens"])
        for p in data["panels"]:
            involved = p["model"]["label"] in d["supports"] + d["weakens"]
            assert (d in p["disagreements"]) == involved


# ---- validators ----

EVIDENCE = {"items": [{"id": "E1", "label": "Revenue", "value": "$13.38B"},
                      {"id": "E2", "label": "Revenue change", "value": "+6.7%"}]}


def test_numbers_must_come_from_the_cited_evidence():
    out = strategy_lab.validate_output(json.dumps({
        "analysis": "Revenue was $13.38B and margins were 40%.",
        "claims": [{"text": "Revenue grew +6.7%.", "evidence_ids": ["E1"], "stance": "bullish"},
                   {"text": "Revenue grew +6.7%.", "evidence_ids": ["E2"], "stance": "supports"}],
        "risks": [], "assumptions": [], "uncertainties": []}), EVIDENCE)
    assert ["number_not_in_evidence"] == out["claims"][0]["issues"] and out["claims"][1]["issues"] == []
    assert out["claims"][0]["stance"] == "neutral"  # unknown stance values are not trusted
    assert any("40%" in v["detail"] for v in out["violations"])
    assert out["checks"]["numbers_traceable"] == {"passed": 1, "total": 2}
    assert out["checks"]["states_uncertainty"] is False


def test_advice_in_analysis_is_withheld_and_missing_keys_fail_schema():
    out = strategy_lab.validate_output('{"analysis": "Prices will rise, so you should buy.", "claims": []}', EVIDENCE)
    assert out["analysis"] == strategy_lab.WITHHELD and out["checks"]["advice_violations"] == 1
    assert out["checks"]["schema_valid"] is False


# ---- requests and gates ----

def test_live_request_is_refused_in_zero_cost_mode(client):
    resp = compare(client, live=True, confirm_live=True)
    body = resp.get_json()
    assert resp.status_code == 403 and body["error"]["code"] == "LIVE_INFERENCE_DISABLED"
    assert "Zero-cost" in body["error"]["message"]


def test_live_request_needs_confirmation(client):
    resp = compare(client, live=True)
    assert resp.status_code == 400 and "confirmed" in resp.get_json()["error"]["message"]


@pytest.mark.parametrize("body, status", [
    ({"scenario": "reckless"}, 400), ({"ticker": "??"}, 400), ({"models": []}, 400),
    ({"models": ["not-a-model"]}, 400), ({"ticker": "ZZZZ"}, 404),
])
def test_bad_requests(client, body, status):
    assert compare(client, **body).status_code == status


def test_model_subset(client):
    panels = compare(client, models=["claude", "qwen"]).get_json()["data"]["panels"]
    assert [p["model"]["key"] for p in panels] == ["claude", "qwen"]


def test_each_gate_blocks_on_its_own(live_ready, monkeypatch):
    qwen, claude = llm_providers.get_model("qwen"), llm_providers.get_model("claude")
    assert llm_providers.live_block_reasons(qwen) == [] == llm_providers.live_block_reasons(claude)
    for attr, value in [("ZERO_COST_MODE", True), ("LAB_LIVE_ENABLED", False), ("LAB_DAILY_BUDGET_USD", "0"),
                        ("LAB_DAILY_BUDGET_USD", "not-a-number"), ("HF_TOKEN", "")]:
        with monkeypatch.context() as m:
            m.setattr(config, attr, value)
            assert len(llm_providers.live_block_reasons(qwen)) == 1, attr
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    assert llm_providers.live_block_reasons(claude) == ["No ANTHROPIC_API_KEY is set."]


def test_provisional_model_blocks_live(live_ready, monkeypatch):
    monkeypatch.setattr(llm_providers, "_registry", None)  # real registry: all provisional
    assert "provisional" in llm_providers.live_block_reasons(llm_providers.get_model("glm"))[0]


# ---- live adapters (fake transports only) ----

def test_hf_adapter_sends_pinned_provider_and_records_actual_cost(live_ready, monkeypatch):
    sent = []
    fake_hf(monkeypatch, '{"analysis": "ok"}', sent)
    out = llm_providers.complete(llm_providers.get_model("qwen"), "sys", "user", 1200, live=True)
    assert out["inference"] == "live" and out["text"] == '{"analysis": "ok"}' and out["error"] is None
    assert sent[0]["json"]["model"] == "Qwen/Qwen3.8-27B:deepinfra" and sent[0]["json"]["temperature"] == 0
    assert sent[0]["headers"]["Authorization"] == "Bearer hf-test-not-real"
    assert sent[0]["url"] == "https://router.huggingface.co/v1/chat/completions"
    assert Decimal(out["cost_usd"]) == Decimal("0.00145") == ledger_today(live_ready)  # 1000*0.20 + 500*2.50 per 1M


def test_budget_refuses_before_any_call(live_ready, monkeypatch):
    sent = []
    fake_hf(monkeypatch, "{}", sent)
    monkeypatch.setattr(config, "LAB_DAILY_BUDGET_USD", "0.000001")
    with pytest.raises(BudgetExceeded):
        llm_providers.complete(llm_providers.get_model("kimi"), "sys", "user", 1200, live=True)
    assert sent == [] and not live_ready.exists()


def test_failed_call_keeps_the_worst_case_reservation(live_ready, monkeypatch):
    def down(*a, **k):
        raise requests.ConnectionError()
    monkeypatch.setattr(requests, "post", down)
    model = llm_providers.get_model("glm")
    out = llm_providers.complete(model, "sys", "user", 1200, live=True)
    assert out["error"] and out["text"] is None
    assert ledger_today(live_ready) == llm_providers.worst_case_usd(model, "sys", "user", 1200)


def test_corrupt_ledger_blocks_live(live_ready, monkeypatch):
    live_ready.write_text("{not json", encoding="utf-8")
    sent = []
    fake_hf(monkeypatch, "{}", sent)
    with pytest.raises(BudgetExceeded):
        llm_providers.complete(llm_providers.get_model("qwen"), "sys", "user", 1200, live=True)
    assert sent == []


def test_anthropic_adapter_uses_registry_model(live_ready, monkeypatch):
    sent = {}

    class Block:
        type, text = "text", '{"analysis": "ok"}'

    class Usage:
        input_tokens, output_tokens = 2000, 100

    class Resp:
        content, usage, stop_reason = [Block()], Usage(), "end_turn"

    class FakeClient:
        def __init__(self, **kw):
            self.messages = self

        def create(self, **kw):
            sent.update(kw)
            return Resp()

    monkeypatch.setattr(llm_providers.anthropic, "Anthropic", FakeClient)
    out = llm_providers.complete(llm_providers.get_model("claude"), "sys", "user", 1200, live=True)
    assert sent["model"] == "claude-sonnet-5-5" and sent["thinking"] == {"type": "between_tools"}
    assert Decimal(out["cost_usd"]) == Decimal("0.005")  # 2000*2.00 + 100*10.00 per 1M


def test_live_compare_is_labelled_live_never_simulated(client, live_ready, monkeypatch):
    mock_json = llm_providers._mock_text(llm_providers.get_model("qwen"),
                                         strategy_lab.build_prompt(strategy_lab.build_evidence("KO"), "balanced")[1])
    fake_hf(monkeypatch, mock_json, [])
    resp = compare(client, models=["qwen", "kimi"], live=True, confirm_live=True)
    data = resp.get_json()["data"]
    assert data["mode"] == "live" and data["simulated_label"] is None and data["notice"] is None
    for p in data["panels"]:
        assert p["simulated"] is False and p["inference"] == "live" and "simulated_label" not in p
        assert p["checks"]["simulated"] is False


def test_live_compare_refuses_whole_run_over_budget(client, live_ready, monkeypatch):
    sent = []
    fake_hf(monkeypatch, "{}", sent)
    monkeypatch.setattr(config, "LAB_DAILY_BUDGET_USD", "0.0001")
    resp = compare(client, live=True, confirm_live=True)
    assert resp.status_code == 402 and sent == []


# ---- page ----

def test_page_has_tabs_and_lab_container(client):
    html = client.get("/").get_data(as_text=True)
    assert 'data-tab="lab"' in html and 'id="lab-root"' in html and 'id="explore-view"' in html
    assert html.index("/static/js/lab.js") < html.index("/static/js/app.js")


def test_lab_js_renders_safely_without_its_own_fetch():
    with open(os.path.join(ROOT, "static", "js", "lab.js"), encoding="utf-8") as f:
        text = f.read()
    assert "innerHTML" not in text and "fetch(" not in text
    assert "simulated_label" in text and "Not a score." in text


def test_check_lab_models_flags_missing_changed_and_matching():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import check_lab_models

    def provider(name, inp, out, status="live", structured=True):
        return {"provider": name, "status": status, "supports_structured_output": structured,
                "pricing": {"input": inp, "output": out}}
    listing = {"data": [
        {"id": "Qwen/Qwen3.8-27B", "providers": [provider("deepinfra", 0.2, 2.5)]},
        {"id": "moonshotai/Kimi-K2.6", "providers": [provider("deepinfra", 0.9, 3.5)]},
        {"id": "openai/gpt-oss-120b", "providers": [provider("deepinfra", 0.037, 0.16999999999999998, "error")]},
    ]}
    rows = {k: (status, note) for k, status, note in check_lab_models.check(llm_providers.registry(), listing)}
    assert rows["qwen"][0] == "OK"
    assert rows["kimi"] == ("CHANGED", "price now 0.9 / 3.5 per M tokens")
    assert rows["gpt-oss"] == ("CHANGED", "status error")
    assert rows["deepseek"][0] == rows["glm"][0] == "MISSING" and rows["claude"][0] == "SKIP"


# ---- zero-cost guard at every AI call site (the SDK can authenticate from a saved login with a blank key) ----

def test_ai_call_sites_refuse_in_zero_cost_mode_even_with_keys_and_gates_open(live_ready, monkeypatch):
    from services import ai_service
    from services.errors import AIUnavailable
    monkeypatch.setattr(config, "ZERO_COST_MODE", True)  # every other gate stays open
    model = llm_providers.get_model("qwen")
    with pytest.raises(LiveInferenceDisabled):
        llm_providers._call_hf(model, "sys", "user", 10)
    with pytest.raises(LiveInferenceDisabled):
        llm_providers._call_anthropic(llm_providers.get_model("claude"), "sys", "user", 10)
    with pytest.raises(AIUnavailable):
        ai_service._call_claude("sys", [{"role": "user", "content": "hi"}], 10)
    with pytest.raises(LiveInferenceDisabled):
        llm_providers.complete(model, "sys", "user", 10, live=True)
    assert not live_ready.exists()  # nothing reserved or spent
