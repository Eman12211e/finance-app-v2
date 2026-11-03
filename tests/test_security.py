"""P6 step 4: security response headers and the CSP (finding F4), the JSON envelope for every /api/ error (F5), log
hygiene (F8), and a sweep for secrets in logs and responses. Offline: Flask's test client only."""
import logging
import os
import re

import pytest

import config
from app import CSP, create_app
from services import paper_engine as eng

ROOT = os.path.join(os.path.dirname(__file__), "..")
SECRET = os.environ["PAPER_STATE_SECRET"]  # set by conftest; it must never reach a log line or a response


# ---- headers ----

@pytest.mark.parametrize("method, path", [("get", "/"), ("get", "/api/health"), ("get", "/static/js/backtest.js"),
                                          ("get", "/api/backtest/guide"), ("post", "/api/backtest/run"),
                                          ("get", "/api/nope"), ("get", "/nope")])
def test_every_response_carries_the_security_headers(client, method, path):
    h = getattr(client, method)(path).headers
    assert h["Content-Security-Policy"] == CSP
    assert (h["X-Content-Type-Options"], h["X-Frame-Options"], h["Referrer-Policy"]) == ("nosniff", "DENY", "no-referrer")
    assert h["Cross-Origin-Opener-Policy"] == "same-origin"


def test_the_csp_allows_only_this_app():
    directives = dict(d.strip().split(" ", 1) for d in CSP.split(";"))
    assert directives["default-src"] == "'self'" and directives["script-src"] == "'self'"
    assert directives["style-src"] == "'self'" and directives["connect-src"] == "'self'"
    assert directives["frame-ancestors"] == "'none'" and directives["object-src"] == "'none'"
    assert "unsafe-inline" not in CSP and "unsafe-eval" not in CSP and "http" not in CSP


def test_the_page_has_nothing_the_csp_would_block():
    with open(os.path.join(ROOT, "templates", "index.html"), encoding="utf-8") as f:
        html = f.read()
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)  # every script is a file
    assert "<style" not in html and not re.search(r'\sstyle="', html) and not re.search(r"\son[a-z]+=", html)
    for src in re.findall(r'(?:src|href)="([^"]+)"', html):
        assert src.startswith("/static/") or src in ("data:,",), src  # nothing from another site


def test_the_frontend_never_writes_html_strings_or_loads_remote_code():
    for name in os.listdir(os.path.join(ROOT, "static", "js")):
        with open(os.path.join(ROOT, "static", "js", name), encoding="utf-8") as f:
            code = f.read()
        assert not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|eval\(|new Function", code), name
        # an injected <style> is blocked by the CSP (found in step 4: chat.js did this; its rules are now in CSS)
        assert not re.search(r"createElement\(\s*['\"]style['\"]|el\(\s*['\"]style['\"]", code), name
        assert not re.search(r"fetch\(\s*['\"]https?:", code), name


# ---- the JSON envelope for every /api/ error ----

def test_unknown_api_paths_answer_not_found_in_json(client):
    resp = client.get("/api/nope")
    env = resp.get_json()
    assert resp.status_code == 404 and env == {"ok": False, "data": None, "source": None, "as_of": None,
                                               "error": {"code": "NOT_FOUND", "message": "That address is not part of this app."}}


@pytest.mark.parametrize("method, path, allowed", [("get", "/api/backtest/run", "OPTIONS, POST"),
                                                    ("post", "/api/backtest/guide", "GET, HEAD, OPTIONS"),
                                                    ("delete", "/api/health", "GET, HEAD, OPTIONS")])
def test_wrong_methods_answer_in_json_and_say_what_is_allowed(client, method, path, allowed):
    resp = getattr(client, method)(path)
    assert resp.status_code == 405 and resp.get_json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert resp.headers["Allow"] == allowed


def test_pages_outside_the_api_keep_the_plain_404(client):
    resp = client.get("/nope")
    assert resp.status_code == 404 and resp.mimetype == "text/html"


def test_an_unexpected_failure_outside_any_route_handler_answers_without_details():
    app = create_app()
    app.add_url_rule("/api/_boom", "boom", lambda: 1 / 0)
    resp = app.test_client().get("/api/_boom")
    assert resp.status_code == 500 and resp.get_json()["error"] == {"code": "INTERNAL_ERROR",
                                                                    "message": "Something went wrong. Please try again."}
    assert b"ZeroDivisionError" not in resp.data and b"Traceback" not in resp.data


# ---- logs and responses never carry secrets; user values are logged quoted ----

def test_a_user_value_with_line_breaks_cannot_forge_a_log_line(client, caplog, monkeypatch):
    from routes import documents as route
    # the id pattern already refuses this value; relax it to reach the logging line (defence in depth)
    monkeypatch.setattr(route, "_DOC_ID", re.compile(".*", re.S))
    monkeypatch.setattr(route.documents, "get_document", lambda doc_id: 1 / 0)
    with caplog.at_level(logging.ERROR):
        client.get("/api/documents/x%0AERROR forged line")
    messages = [r.getMessage() for r in caplog.records]
    assert any("id='x\\nERROR forged line'" in m for m in messages), messages
    assert not any("\nERROR forged line" in m for m in messages)


def test_secrets_never_reach_logs_or_replies(client, caplog):
    state = eng.new_state("synthetic-b")
    tampered = dict(state, sig="0" * len(state["sig"]))
    with caplog.at_level(logging.DEBUG):
        replies = [
            client.post("/api/paper/view", json={"state": state}),
            client.post("/api/paper/view", json={"state": tampered}),
            client.post("/api/backtest/run", json={"state": tampered, "symbol": "SYN-HLT1", "preset": "sma_cross",
                                                   "costs": "none"}),
            client.post("/api/analysis/indicators", json={"state": [], "symbol": 1}),
            client.get("/api/health"),
        ]
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert SECRET not in logged and state["sig"] not in logged  # no key, no signature, no session body
    for r in replies:
        assert SECRET.encode() not in r.data
    health = client.get("/api/health").get_json()["data"]
    assert set(health["keys_present"].values()) == {False}  # zero-cost mode: says whether keys exist, never what


def test_request_bodies_over_the_limit_are_refused_before_any_route_runs(client):
    # found in step 4: chat, lab and sentiment answered 500 INTERNAL_ERROR (and logged a traceback) here
    for path in ("/api/backtest/run", "/api/paper/view", "/api/analysis/indicators", "/api/chat", "/api/lab/compare",
                 "/api/sentiment"):
        resp = client.post(path, data="x" * (config.MAX_REQUEST_BYTES + 1), content_type="application/json")
        assert resp.status_code == 413 and resp.get_json()["error"]["code"] == "REQUEST_TOO_LARGE", path
