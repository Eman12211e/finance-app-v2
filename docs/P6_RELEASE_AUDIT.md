# P6 Step 0 — Release-readiness audit

Date: 2026-11-02. Baseline: `dev/v2` at `c335175` (P5 accepted), working tree clean, local only (11 commits ahead of
`origin/dev/v2`, nothing pushed). Goal: a reliable, free-to-run, beginner-friendly financial education app suitable
for a **controlled release** (a known, small audience, not a public launch).

**Method and its limits.** This is a self-audit by the implementer: the repository, configuration and documentation
were read and the running app was probed with Flask's test client, using the same machine and the same V1 virtual
environment that produced every reported test total. Nothing here is independent verification. "Demonstrated" means
observed directly during this audit (command and result in the Evidence column). "Unverified risk" means plausible but
not shown. Reported passing tests (993 pytest, 480 browser checks in P5) are treated as claims until an independent run
(P6 Step 2) reproduces them.

## Summary

| Severity | Demonstrated defects | Unverified risks | Optional improvements |
|---|---|---|---|
| Critical | 0 | 0 | — |
| High | 2 (F1, F2) | 1 (R1) | — |
| Medium | 4 (F3–F6) | 3 (R2–R4) | — |
| Low | 4 (F7–F10) | 1 (R5) | 4 (I1–I4) |

No Critical finding: nothing is deployed, the app is reachable only on `127.0.0.1`, no real money, orders or accounts
exist, and zero-cost mode blocks every paid or metered call by default.

**Release blockers (must be resolved before any release):** F1, F2, R1. F3–F6 and R2–R4 should be resolved or
explicitly accepted by the owner before the release-candidate gate (P6 Step 8).

## Demonstrated defects

| ID | Sev. | Area | Finding | Evidence | Recommendation (step) |
|---|---|---|---|---|---|
| F1 | High | Test reproducibility, independent verification | Every test total since P1 was produced by the implementer on one machine, using **another repository's** virtual environment (`beginner-friendly-finance-app\venv`, Python 3.12.10). This repository has no `venv`, no CI (`.github/` absent) and no record of a clean install. The README's setup (`python -m venv venv`, `pip install -r requirements.txt`) has not been exercised for V2. | `ls` (no `venv/`, no `.github/`); every P5 command used the V1 interpreter; README "Setup". | A clean-environment install and test run (Step 1) and an independently executed CI workflow (Step 2). |
| F2 | High | Production runtime | The only way to run the app is `python app.py`, Flask's development server (Werkzeug), which the Flask documentation says is not for production. There is no production entry point, host or port setting, worker limit or logging setting. `logging.basicConfig(level=INFO)` is the only logging configuration. | `app.py` line 52: `create_app().run(port=5000, debug=False)`; no WSGI server in `requirements.txt`. | A production entry point with a pure-Python WSGI server (proposed: Waitress, a **new dependency needing owner approval**) bound to `127.0.0.1` by default, plus documented settings (Step 3). |
| F3 | Medium | Dependency reproducibility | Only top-level packages are pinned; transitive packages (Werkzeug 3.1.9, Jinja2 3.1.6, …) are not, so a later install can differ. Runtime, test and build tools are mixed in one file (`pytest`; `yfinance`, used only by `scripts/build_demo_data.py`; `anthropic`, unused while zero-cost mode is on). No Python version is declared. | `requirements.txt`; `pip freeze` of the test interpreter shows unpinned Werkzeug and Jinja2. | Split runtime / dev / build requirements, add a full lock generated with `pip freeze` (no new tool), and declare Python 3.12 (Step 1). |
| F4 | Medium | Security headers | No response sets `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options` / `frame-ancestors` or `Referrer-Policy`. Rendering is text-only (no `innerHTML`, `insertAdjacentHTML` or `document.write` in `static/js`; Jinja autoescaping), so no XSS is known, but there is no second line of defence and the page can be framed. | Test client `GET /` headers: none of these; `grep innerHTML static/js` returns nothing. | Add the headers in one `after_request` hook. A strict CSP (`default-src 'self'`) looks feasible: `templates/index.html` has no inline scripts, `style=` attributes or event-handler attributes (its 18 scripts are all external). Confirm in the browser suites (Step 4). |
| F5 | Medium | Error handling (API contract) | Unknown `/api/...` paths and wrong methods return Flask's **HTML** 404 / 405 pages, not the standard JSON envelope. `static/js/api.js` then fails to parse JSON and shows "Could not reach the server.", which misdescribes the problem. | `GET /api/nope` → 404 `text/html`; `GET /api/backtest/run` → 405 `text/html`. | JSON envelopes for 404 / 405 under `/api/` (`NOT_FOUND`, `METHOD_NOT_ALLOWED`), documented in the API contract (Step 4). |
| F6 | Medium | Startup diagnostics | Invalid environment values stop the app at import with a raw traceback (for example `LAB_MAX_TOKENS=abc` → `int()` `ValueError` in `config.py`). There is no startup check that the required data files (scenarios, guides, documents) load, so a damaged file shows up only when a user opens that tab. | Run with `LAB_MAX_TOKENS=abc`: `python -c "import config"` → `ValueError: invalid literal for int() with base 10: 'abc'`; `LAB_TIMEOUT_SECONDS` is parsed the same way. | A startup self-check with plain-language messages and a non-zero exit, plus a `--check` mode (Step 3). |
| F7 | Low | Repository hygiene | `data/endpoint_check.json` is tracked, but `scripts/check_endpoints.py` rewrites it on every run, so each check leaves the working tree dirty (restored by hand with `git checkout` throughout P5). | P5 evidence logs. | Write the check's output outside the repository, or stop tracking the file (Step 1). |
| F8 | Low | Logging | User-supplied identifiers are logged unescaped (`log.exception("document get failed for id=%s", doc_id)`, `ticker=%s`), so a value containing line breaks can forge log lines. | `routes/documents.py:36`, `routes/stocks.py:23`, `routes/earnings.py:27`. | Log `repr()` of user values, or values already validated against an allowlist (Step 4). |
| F9 | Low | Documentation | The README describes Windows PowerShell only; its test command assumes a project `venv` that does not exist (F1). The roadmap v3 referenced by the P5 brief is not in the repository. The `docs/` folder has no index of which documents are current. | README; `docs/`. | First-run documentation for Windows and macOS / Linux, troubleshooting, and a docs index (Step 7). |
| F10 | Low | Static assets | Static files are served without cache headers or version strings (the chart library is 193 KB, `paper.js` 100 KB), so every reload re-requests about 450 KB of assets. This is harmless locally. | Test client sizes; no `Cache-Control`. | Optional: a cache lifetime for `/static/vendor/` only, or accept as-is for a local app (Step 6). |

## Unverified risks

| ID | Sev. | Area | Risk | Why not demonstrated | Recommendation (step) |
|---|---|---|---|---|---|
| R1 | High | Licensing and data provenance | (a) The repository has **no LICENSE**, so others have no right to use it. (b) `data/demo_stocks.json` (Explore tab) was generated from Yahoo Finance via `yfinance` for real companies (AAPL, MSFT, KO, NVDA, VOO), and its redistribution terms are unknown. (c) `data/brokerages/*.json` states facts about real firms (Fidelity, Interactive Brokers, Robinhood, Schwab) that can go out of date, and uses their names. (d) Optional FinBERT weights are CC BY-NC-SA 4.0 (non-commercial); they are not bundled. | Legal terms were not reviewed; no legal judgement is made here. | Owner decisions: a project licence; replace the Explore data with synthetic data, keep it with attribution and a "not current" label, or remove it; a review date and source for each brokerage fact; a third-party notices file (Step 5). |
| R2 | Medium | Accessibility outside P5 | P5's view was audited in depth. The other tabs (Explore, AI Lab, Understand Before You Sign, Compare Brokerages, and the trading workspace) have the automated visual audit (contrast, names, targets, overflow) and the workflow suite, but no real screen-reader pass (NVDA, VoiceOver) and no real-device touch test anywhere. Automated checks cannot confirm reading order, announcements or how understandable the content is. | No assistive technology was run; phones were emulated. | A keyboard audit suite for every tab, then a manual NVDA (free) and phone checklist done by a person (Step 6). |
| R3 | Medium | Load and abuse on a shared host | No rate limit or concurrency cap. Each request is cheap (a Day 250 backtest takes about 25 ms in-process and returns 46 KB), but nothing bounds request volume if the app were reachable by others. | Measured on a single client only. | Keep the release single-user on `127.0.0.1`, or add a simple in-process limit with the WSGI server's thread cap. Owner decision on the deployment model (Steps 3–4). |
| R4 | Medium | Third-party facts in the content | The Accounts 101, Sign and Brokers tabs quote rules and figures (IRS limits, firm fees) that change over time. Each brokerage fact carries a "checked" date, but nothing warns when that date is old. | No check of the facts against current sources was made. | A review-date policy, a visible "checked on" date and a test that flags facts older than the policy (Step 5). |
| R5 | Low | Practice-session replay | The practice session is stored in the browser and signed (HMAC-SHA256, constant-time comparison). A user can restore an older validly signed copy of their own session (for example undo a bad trade). It involves no real money and no other user, so it is an accepted educational limitation. | By design. | Document it as accepted; no change (Step 4). |

## Optional improvements (not blockers)

| ID | Sev. | Idea |
|---|---|---|
| I1 | Low | `pip-audit` in CI for known-vulnerable packages (a dev-only tool; needs approval as a new dependency). |
| I2 | Low | A single `scripts/check_all` (PowerShell and sh) running pytest and the browser suites one by one, as the evidence runs did by hand. |
| I3 | Low | A tiny synthetic "fixture" market for faster browser suites in CI. |
| I4 | Low | Show the app version and commit in the footer or `/api/health`, for bug reports. |

## Confirmed in this audit (self-observed, still to be confirmed independently)

- **Zero-cost default:** `ZERO_COST_MODE` is on unless set to `0`; keys are blanked and demo data forced (`config.py`). Tests block all network calls (`tests/conftest.py`).
- **Offline:** no CDN or remote resource. Every external URL in the templates and JS is an outbound link (investor.gov, finra.org, irs.gov, tradingview.com credit). Lightweight Charts 5.2.1 is vendored with its Apache-2.0 LICENSE and NOTICE and hash-pinned by a test.
- **Rendering:** text nodes only (no HTML-string sinks); Jinja autoescaping.
- **Sessions:** HMAC-SHA256 with `hmac.compare_digest`; the key comes from `PAPER_STATE_SECRET` or a local key file, created atomically and gitignored. `.env` and `data/paper_state.key` are untracked; only `.env.example` is tracked.
- **Input limits:** a 64 KB request limit answers a JSON 413. Each endpoint validates exact fields and types, with fuzz tests (P4 and P5). *Correction (Step 4): not true for every route. See F11.*
- **Errors:** route errors use the JSON envelope with a generic message and are logged server-side (no stack traces sent). F5 is the exception.
- **No real transactions:** practice trading and strategy tests are synthetic and fictional; the education footer appears on every page; P5 results carry the standing note.
- **Performance:** about 25 ms per Day 250 backtest; page shell 7 KB plus about 450 KB of scripts and styles, served locally.

## Found during P6 Steps 1–4 (all fixed)

| ID | Sev. | Area | Finding | Fixed in |
|---|---|---|---|---|
| F11 | Medium | Request limits | The chat, AI Lab and sentiment endpoints answered a body over 64 KB with **500 `INTERNAL_ERROR`** and logged a traceback, instead of the JSON 413: their broad `except Exception` swallowed the size error. Step 0 wrongly listed the limit as confirmed for every route. | Step 4: the limit is checked in `before_request`, before any route runs; a test covers six POST endpoints |
| F12 | Medium | CSP compatibility | `static/js/chat.js` (from V1) injected its CSS as a `<style>` element. The strict CSP blocks it, so the chat panel would lose its styling. Found by the new violation check in the visual audit. | Step 4: the 15 rules moved unchanged to `features.css`; a test forbids injected `<style>` |
| F13 | Low | Environment | On Windows without long-path support, installing `anthropic` fails in a deeply nested folder. | Step 1: README asks for a short project path; `check_all` uses short temporary paths |
| F14 | Low | Data loss | A keyless `check_endpoints.py` run overwrote the last real `data/endpoint_check.json` (read by live mode) with SKIP rows. It was more than the dirty tree described in F7. | Step 1: a run that checks nothing leaves the file alone (test) |

Status of the Step 0 findings after Step 4:
- **Fixed:** F2, F3, F4, F5, F6, F7, F8.
- **F1, partly fixed:**
  - clean installs are reproduced: two clean environments, and installed packages equal the lock;
  - the CI workflow is written;
  - **external CI has not run**, so there is still no independent verification.
- **Open:**
  - R1 and R4: Step 5, owner decisions;
  - R2, F9 and F10: Steps 6–7;
  - R3 and R5: accepted risks pending owner confirmation, described in `docs/SECURITY.md`.
