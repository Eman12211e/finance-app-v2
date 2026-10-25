"""Optional Sentiment Explorer: disabled mode, real-vs-unavailable provenance, bad ids, caching, no fabricated labels.
FinBERT is replaced by a fake pipeline; transformers/torch are not needed or imported."""
import re
import sys

import pytest

import config
from services import ai_service, sentiment_service


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(sentiment_service, "_pipeline", None)
    monkeypatch.setattr(sentiment_service, "_load_error", None)
    monkeypatch.setattr(sentiment_service, "_results", {})

    def no_claude(*a, **k):
        raise AssertionError("the Sentiment Explorer must never call Claude")
    monkeypatch.setattr(ai_service, "_call_claude", no_claude)


class FakePipe:
    """Stands in for transformers' text-classification pipeline (top_k=None output shape)."""

    def __init__(self, scores=None, nested=False, error=None):
        self.scores = scores or {"positive": 0.9, "negative": 0.04, "neutral": 0.06}
        self.nested, self.error, self.calls = nested, error, []

    def __call__(self, text):
        self.calls.append(text)
        if self.error:
            raise self.error
        out = [{"label": k, "score": v} for k, v in self.scores.items()]
        return [out] if self.nested else out


def enable(monkeypatch, pipe=None, load_error=None):
    monkeypatch.setattr(config, "SENTIMENT_ENABLED", True)
    loads = []

    def load():
        loads.append(1)
        if load_error:
            raise load_error
        return pipe
    monkeypatch.setattr(sentiment_service, "_load_pipeline", load)
    return loads


def post(client, statement_id):
    return client.post("/api/sentiment", json={"statement_id": statement_id})


def test_disabled_by_default_returns_unavailable_without_loading(client, monkeypatch):
    assert config.SENTIMENT_ENABLED is False
    loads = []
    monkeypatch.setattr(sentiment_service, "_load_pipeline", lambda: loads.append(1))
    listing = client.get("/api/sentiment/statements").get_json()
    assert listing["ok"] is True and listing["data"]["enabled"] is False
    body = post(client, "outlook-raised").get_json()
    assert body["ok"] is True and body["source"] is None
    d = body["data"]
    assert d["inference"] == "unavailable" and d["label"] is None and d["scores"] is None
    assert d["reason"] == "The Sentiment Explorer is turned off." and loads == []


def test_real_model_result_is_labelled_model(client, monkeypatch):
    pipe = FakePipe({"positive": 0.1, "negative": 0.85, "neutral": 0.05})
    enable(monkeypatch, pipe)
    d = post(client, "investigation").get_json()["data"]
    assert d["inference"] == "model" and d["model"] == "ProsusAI/finbert" and d["reason"] is None
    assert d["label"] == "negative"  # highest model score, never chosen by us
    assert d["scores"]["negative"] == {"value": 85.0, "display": "85.00%"}
    assert set(d["scores"]) == {"positive", "negative", "neutral"}
    assert pipe.calls == ["Regulators opened an investigation into the company's accounting practices."]


def test_nested_pipeline_output_is_accepted(client, monkeypatch):
    enable(monkeypatch, FakePipe({"positive": 0.2, "negative": 0.1, "neutral": 0.7}, nested=True))
    assert post(client, "annual-meeting").get_json()["data"]["label"] == "neutral"


def test_load_failure_is_unavailable_and_not_retried(client, monkeypatch):
    loads = enable(monkeypatch, load_error=ImportError("No module named 'transformers'"))
    for sid in ("outlook-raised", "supply-deal"):
        d = post(client, sid).get_json()["data"]
        assert d["inference"] == "unavailable" and d["label"] is None and d["scores"] is None
        assert d["reason"] == "The sentiment model is not installed or could not be loaded on this computer."
    assert len(loads) == 1


def test_inference_failure_is_unavailable(client, monkeypatch):
    enable(monkeypatch, FakePipe(error=RuntimeError("boom")))
    d = post(client, "new-cfo").get_json()["data"]
    assert d["inference"] == "unavailable" and d["label"] is None


def test_unexpected_labels_are_unavailable_not_guessed(client, monkeypatch):
    enable(monkeypatch, FakePipe({"LABEL_0": 0.9, "LABEL_1": 0.05, "LABEL_2": 0.05}))
    d = post(client, "outlook-raised").get_json()["data"]
    assert d["inference"] == "unavailable" and d["label"] is None and d["scores"] is None


def test_results_are_cached_per_statement(client, monkeypatch):
    pipe = FakePipe()
    enable(monkeypatch, pipe)
    first = post(client, "supply-deal").get_json()["data"]
    second = post(client, "supply-deal").get_json()["data"]
    assert first == second and len(pipe.calls) == 1


@pytest.mark.parametrize("body", [{"statement_id": "not-a-statement"}, {"statement_id": ""}, {}, None, {"statement_id": 3}])
def test_bad_ids_are_invalid_request(client, body):
    resp = client.post("/api/sentiment", json=body) if body is not None else client.post("/api/sentiment", data="x")
    assert resp.status_code == 400 and resp.get_json()["error"]["code"] == "INVALID_REQUEST"


def test_statements_are_fictional_and_contain_no_figures(client):
    data = client.get("/api/sentiment/statements").get_json()["data"]
    assert data["note"].startswith("These example statements are fictional")
    ids = [s["id"] for s in data["statements"]]
    assert len(ids) == len(set(ids)) >= 3
    assert all(not re.search(r"\d|\$|%", s["text"]) for s in data["statements"])


def test_transformers_is_never_imported_in_normal_runs(client):
    post(client, "outlook-raised")
    assert "transformers" not in sys.modules and "torch" not in sys.modules


def test_page_has_hidden_button_container_and_script(client):
    html = client.get("/").get_data(as_text=True)
    assert '<button id="sentiment-open" type="button" class="button-secondary" hidden>Sentiment Explorer</button>' in html
    assert 'id="sentiment-root"' in html
    assert html.index("/static/js/accounts.js") < html.index("/static/js/sentiment.js") < html.index("/static/js/app.js")
