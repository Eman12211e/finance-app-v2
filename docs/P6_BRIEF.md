# P6 — Release preparation: brief and roadmap

Status: **Step 0 (this plan) for owner review.** Nothing in Steps 1–8 is started.
Baseline: `dev/v2` at `c335175`; findings: `docs/P6_RELEASE_AUDIT.md`; progress: `docs/P6_PROGRESS.md`.

## Goal

A reliable, free-to-run, beginner-friendly financial education app, ready for a **controlled release**: run by a known,
small audience on their own computers (or one machine on a private network), from a clean install, with independently
executed tests. It is not a public hosted launch. A hosted deployment would be a later decision.

## Boundaries (all steps)

- Synthetic practice data throughout. No real brokerage integration, no external market-data feed, no paid service,
  no real trading. `ZERO_COST_MODE` stays on by default.
- No new product features. Preserve P1–P5 behaviour. Protected files (`services/paper_engine.py`,
  `services/paper_market.py`, `routes/paper.py`, `data/paper/scenarios/*.json`, `scripts/build_synthetic_scenario.py`,
  `static/vendor/lightweight-charts/*`) are not changed. The P4 and P5 engines change only for a demonstrated defect,
  with owner approval.
- No Graphify or TradingView MCP. A new dependency only where this brief names it, and only after owner approval at that
  step.
- No push, merge, tag, deployment, publication, or enabling of an external CI service without the owner's explicit
  authorization for that action.
- Commits use the owner's Git identity with no AI attribution lines (project rule).

## Release blockers carried into the plan

| Finding | Blocker? | Resolved in |
|---|---|---|
| F1 no clean install, no independent test run | **Yes** | Steps 1–2 |
| F2 development server only | **Yes** | Step 3 |
| R1 licence and data provenance | **Yes** (owner decisions) | Step 5 |
| F3 dependency pinning, F6 startup diagnostics | Before the release-candidate gate | Steps 1, 3 |
| F4 security headers, F5 JSON 404 / 405, F8 log hygiene | Before the release-candidate gate | Step 4 |
| R2 accessibility outside P5, R3 load and abuse, R4 dated facts | Resolve or owner-accept before the release-candidate gate | Steps 3–6 |
| F7, F9, F10, R5, I1–I4 | No | Steps 1, 4, 6, 7 |

## Independent verification (CI) proposal

**What "independent" means here:** the tests run on a machine the implementer does not control, from a clean checkout
and a clean install of the locked requirements, and the results are read from that run's log, not from the
implementer's report.

**Proposed workflow** (`.github/workflows/ci.yml`, added in Step 2 only with approval; it runs only once the owner
pushes, which is a separate authorization). On GitHub's hosted Ubuntu runner:

1. Check out the commit; Python 3.12; `pip install -r requirements-dev.lock` (Step 1).
2. Deterministic checks: `python -m pytest -q -p no:cacheprovider` with `ZERO_COST_MODE=1` (the conftest network
   block applies). This covers the exact-reference maths, API security and fuzz tests, content integrity, and the
   protected-file and vendored-library hash pins.
3. Browser smoke tests: Node 22 and the runner's preinstalled Google Chrome;
   `BROWSER=/usr/bin/google-chrome node scripts/qa/run.mjs ci-qa workflows backtest visual_audit`, run against the app
   it starts on `127.0.0.1` in zero-cost demo mode.
4. Upload the pytest log and `ci-qa/` (results and screenshots) as run artifacts.
5. Optional (I1, approval needed): `pip-audit -r requirements.lock`.

**Cost:** GitHub Actions is free for public repositories, and private repositories on the Free plan include a monthly
allowance of hosted minutes (2,000 at the time of writing; the owner should confirm the current terms). One run is
expected to take about 10–15 minutes, most of it browser suites. No other paid service.

**If CI is not authorized:** Step 2 still delivers `scripts/check_all.ps1` and `scripts/check_all.sh`. They create a
fresh virtual environment in a temporary folder, install the lock, and run pytest and each browser suite one by one,
writing logs. Anyone can run them on another machine and compare. That is reproducible, but **not independent** unless
someone other than the implementer runs it. The report will say so.

## Steps

Every step ends with a local commit, a report in the format at the end of this brief, and a hard stop for owner
review. Each step begins with the "Resolve before next step" list in `docs/P6_PROGRESS.md`.

### Step 0 — Release-readiness audit and plan (this document)

- **Deliverables:** `docs/P6_RELEASE_AUDIT.md`, `docs/P6_BRIEF.md`, `docs/P6_PROGRESS.md`.
- **Non-goals:** any code or configuration change.
- **Gate:** owner approves the audit, the roadmap and the decisions listed under Step 0 in the progress log.

### Step 1 — Reproducible environment and clean install (F1 part, F3, F7)

- **Scope:** declare Python 3.12 (README and `.python-version`). Split the requirements:
  - `requirements.txt`: runtime only;
  - `requirements-dev.txt`: pytest;
  - `requirements-build.txt`: yfinance, for the demo-data script;
  - each with a full `pip freeze` lock (`requirements.lock`, `requirements-dev.lock`). The sentiment file stays optional.

  Then do a clean install into **this repository's own** new `venv` and run the full suite there. Move
  `endpoint_check.json` output out of the tracked tree, or untrack it.
- **Non-goals:** upgrading any package version; Docker.
- **Files:** `requirements*.txt` and `*.lock`, `.python-version`, `.gitignore`, `scripts/check_endpoints.py` (output
  path only), `README.md` (setup only), `tests/` (the import of `anthropic` and `requests` in `conftest.py` remains
  valid).
- **Validation:**
  - a fresh venv from the lock installs without errors;
  - `pytest` in that venv gives the same pass count as the V1 interpreter, with nothing skipped that wasn't skipped before;
  - `pip check` is clean;
  - the app starts from that venv;
  - the browser suites pass using that venv's Python.
- **Evidence:** install log, `pip freeze`, pytest log, browser results, `git status`.
- **Dependencies and blockers:** network access to PyPI to install the pinned packages, which needs **owner approval**
  (installing dependencies).
- **Gate:** owner approves the split, the lock and the clean-install evidence.

### Step 2 — Independent verification pathway (F1)

- **Scope:** `.github/workflows/ci.yml` as proposed above (written, **not pushed**), `scripts/check_all.ps1` and `.sh`,
  and a CI section in the README. Make the browser runner work on Linux Chrome: `run.mjs` already lists
  `/usr/bin/google-chrome`; check the paths and fonts.
- **Non-goals:** enabling the workflow; branch protection; any paid runner.
- **Files:** `.github/workflows/ci.yml`, `scripts/check_all.*`, `scripts/qa/run.mjs` (only if Linux needs it),
  `README.md`.
- **Validation:**
  - the workflow file passes a YAML syntax check;
  - `check_all` runs end to end on this machine from a fresh temporary venv;
  - **if the owner authorizes a push**, the first CI run's own log is the independent result, and any difference from
    the local totals is investigated, not explained away.
- **Evidence:** the `check_all` logs; with authorization, the CI run link and artifacts.
- **Dependencies:** Step 1's lock. A push needs **separate owner authorization**.
- **Gate:** owner decides between (a) authorizing a push so CI runs, or (b) local `check_all` only, with the limit
  stated in every later report.

### Step 3 — Production runtime, configuration and startup checks (F2, F6, R3 part)

- **Scope:**
  - a production entry point `serve.py` on **Waitress**, a pure-Python WSGI server that works on Windows; it is a
    **new runtime dependency and needs owner approval**;
  - bind to `127.0.0.1` by default; `HOST`, `PORT` and `THREADS` settings, validated;
  - validated parsing of every environment value, with plain-language errors and a non-zero exit;
  - a startup self-check that loads every data file and guide and confirms the signing key is available; a
    `python serve.py --check` mode;
  - production logging at WARNING by default, with no request bodies logged;
  - "development" (`app.py`) versus "release" (`serve.py`) documented.
- **Non-goals:** HTTPS termination, a reverse proxy, hosting, user accounts.
- **Files:** `serve.py` (new), `config.py` (validation only), `app.py` (logging setup only), `requirements*.txt`,
  `README.md`, `tests/test_startup.py` (new).
- **Validation:**
  - tests for every invalid setting;
  - the self-check fails clearly for a missing or damaged data file and a bad key path;
  - `serve.py` serves the app and the browser suites pass against it;
  - zero-cost mode still defaults on.
- **Evidence:** test logs, startup output (good and bad configurations), browser results against `serve.py`.
- **Gate:** owner approves Waitress (or picks an alternative) before work starts, and approves the result.

### Step 4 — Security hardening (F4, F5, F8, R3 part, R5)

- **Scope:**
  - security headers (CSP `default-src 'self'`, `frame-ancestors 'none'`, nosniff, `Referrer-Policy: no-referrer`) in
    one hook;
  - JSON envelopes for `/api/` 404 and 405;
  - `api.js` told apart "could not reach" from other errors;
  - user values logged as `repr()`;
  - a written threat model for the controlled release (single user, local), with R5 documented as accepted;
  - optional `pip-audit` (I1) if approved.
- **Non-goals:** authentication, user accounts, a WAF, rate limiting beyond the WSGI thread cap (unless the owner picks
  a shared-host model in Step 3).
- **Files:** `app.py`, `routes/envelope.py`, `services/errors.py`, `static/js/api.js`, `docs/API_CONTRACT.md`,
  `docs/SECURITY.md` (new), tests.
- **Validation:**
  - header tests on every route;
  - the whole browser suite set passes under the CSP with no console CSP violations;
  - 404 and 405 envelope tests;
  - the existing fuzz tests;
  - a re-run of the XSS-sink grep;
  - confirm that no secret, key or session body appears in logs (a test captures the logs).
- **Evidence:** test logs, browser results, the threat model.
- **Gate:** owner approves the CSP, the threat model and the accepted risks.

### Step 5 — Licensing, attribution and data provenance (R1, R4)

- **Scope:** carry out the owner's decisions:
  - a project LICENSE;
  - `THIRD_PARTY_NOTICES.md` (Lightweight Charts Apache-2.0, Python packages, optional FinBERT CC BY-NC-SA);
  - the Explore tab's `demo_stocks.json`: replace with synthetic, label it, or remove it;
  - a source and review date for every brokerage and tax fact, a visible "checked on" date, and a test that flags facts
    older than the agreed policy;
  - review of disclaimers and the "no real transactions" statements across all tabs.
- **Non-goals:** legal advice (decisions are the owner's); refreshing facts from live sources automatically.
- **Files:** `LICENSE`, `THIRD_PARTY_NOTICES.md`, `data/demo_stocks.json` or its replacement, `data/brokerages/*.json`
  (dates only, or as decided), affected `static/js/*` text, tests.
- **Validation:**
  - every third-party asset is listed;
  - the date-policy test;
  - content tests still pass;
  - the visual audit is clean.
- **Dependencies:** **owner decisions** on the licence, the Explore data and the review-date policy, made before the step
  starts.
- **Gate:** owner approves the licence text, the notices and the data outcome.

### Step 6 — Accessibility, mobile and performance release audit (R2, F10)

- **Scope:**
  - extend the keyboard and focus checks (as P5's) to every tab;
  - a manual checklist for NVDA (free), Windows Narrator and a real phone, to be **performed by a person**;
  - fix demonstrated defects;
  - measure page weight and timings;
  - an optional `/static/vendor/` cache lifetime.
- **Non-goals:** redesigns; new components.
- **Files:** `scripts/qa/*`, CSS and JS fixes for demonstrated defects only, `docs/ACCESSIBILITY.md` (new).
- **Validation:**
  - automated suites pass at 1280 and 390 px, light and dark, reduced motion and 200% zoom;
  - the manual checklist is completed and signed off by a person (or explicitly deferred).
- **Evidence:** suite results, screenshots, the completed checklist.
- **Gate:** owner reviews the manual results, or accepts their deferral as a known limitation.

### Step 7 — Documentation and first-run experience (F9)

- **Scope:**
  - a README for install, run (development and release), test, CI and troubleshooting, on Windows and macOS / Linux;
  - `docs/README.md` (an index of current versus historical documents);
  - `CHANGELOG.md` / release notes;
  - an updated demo script and the known limitations;
  - commit the roadmap v3 to the repository if the owner provides it.
- **Non-goals:** marketing content.
- **Files:** `README.md`, `docs/README.md`, `CHANGELOG.md`, `docs/DEMO_SCRIPT.md`.
- **Validation:** a person, or a fresh-venv run, follows the README word for word on a clean folder; every command in it
  is tested.
- **Gate:** owner approves the documentation.

### Step 8 — Release-candidate QA and sign-off

- **Scope:**
  - the full suite set via `check_all`, and via CI if authorized;
  - confirm every finding is resolved or accepted in writing;
  - a final evidence folder `..\finance-app-v2-screenshots\P6\final\`;
  - a release-candidate report;
  - a proposed version number and tag name (**no tag without approval**).
- **Non-goals:** deployment; publication.
- **Validation:**
  - independent CI green, or the stated limitation;
  - the protected-file hashes;
  - zero-cost and offline checks;
  - a clean working tree.
- **Gate:** owner decides on release, tag, push and merge, each separately.

## Report-back format (every step)

1. Branch, commit hash(es), working-tree status.
2. What changed (files) and what was deliberately not done.
3. Validation results with exact totals, **marked self-run or independent (CI)**, and log locations.
4. Findings resolved, findings opened, risks accepted (with the owner's decision where needed).
5. Evidence folder (`..\finance-app-v2-screenshots\P6\step-N\`).
6. Known limitations.
7. The exact approval needed next.
