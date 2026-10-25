# Owner: Integrator. Optional Sentiment Explorer: ONLY file that loads the FinBERT model (transformers).
# Never fabricates a label: if the model cannot run, the result is "unavailable" with no classification.
import json
import logging
import os
import threading

import config
from services.errors import InvalidRequest
from services.formatting import field, pct_level

log = logging.getLogger(__name__)
STATEMENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sentiment_statements.json")
LABELS = ("positive", "negative", "neutral")

_statements = None
_pipeline = None
_load_error = None  # set once per process if loading fails, so a broken install is not retried on every click
_results = {}
_lock = threading.Lock()


def statements():
    global _statements
    if _statements is None:
        with open(STATEMENTS_PATH, encoding="utf-8") as f:
            _statements = json.load(f)
    return _statements


def _load_pipeline():
    """Load FinBERT from the local Hugging Face cache only; never downloads during a request."""
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline  # optional dependency

    tokenizer = AutoTokenizer.from_pretrained(config.SENTIMENT_MODEL, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(config.SENTIMENT_MODEL, local_files_only=True)
    return pipeline("text-classification", model=model, tokenizer=tokenizer, top_k=None, device=-1)


def _get_pipeline():
    global _pipeline, _load_error
    with _lock:
        if _pipeline is None and _load_error is None:
            try:
                _pipeline = _load_pipeline()
                log.info("sentiment model loaded: %s", config.SENTIMENT_MODEL)
            except Exception as exc:
                _load_error = "The sentiment model is not installed or could not be loaded on this computer."
                log.warning("sentiment model unavailable: %s", type(exc).__name__)
    return _pipeline, _load_error


def _unavailable(statement, reason):
    return {"statement_id": statement["id"], "text": statement["text"], "model": config.SENTIMENT_MODEL,
            "inference": "unavailable", "label": None, "scores": None, "reason": reason}


def classify(statement_id):
    statement = next((s for s in statements()["statements"] if s["id"] == statement_id), None)
    if statement is None:
        raise InvalidRequest("Please choose one of the example statements.")
    if not config.SENTIMENT_ENABLED:
        return _unavailable(statement, "The Sentiment Explorer is turned off.")
    if statement_id in _results:
        return _results[statement_id]

    pipe, error = _get_pipeline()
    if pipe is None:
        return _unavailable(statement, error)
    try:
        out = pipe(statement["text"])
        if out and isinstance(out[0], list):  # some versions nest one list per input
            out = out[0]
        scores = {str(d["label"]).lower(): float(d["score"]) for d in out}
    except Exception as exc:
        log.warning("sentiment inference failed: %s", type(exc).__name__)
        return _unavailable(statement, "The sentiment model could not classify this statement.")
    if set(scores) != set(LABELS):
        log.warning("sentiment model returned unexpected labels: %s", sorted(scores))
        return _unavailable(statement, "The sentiment model returned an unexpected result.")

    result = {
        "statement_id": statement["id"], "text": statement["text"], "model": config.SENTIMENT_MODEL,
        "inference": "model",
        "label": max(scores, key=scores.get),
        "scores": {k: field(scores[k] * 100, pct_level) for k in LABELS},  # model probabilities as percent
        "reason": None,
    }
    _results[statement_id] = result  # only real model results are cached
    return result
