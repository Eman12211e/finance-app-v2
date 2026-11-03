# Finance App V2
Most AI finance tools try to tell you what to do with your money. This project takes a different approach. It uses AI to make complicated financial information understandable, while leaving the analysis and decisions to the user. The goal isn't to replace financial judgment. It's to help people develop it.

A beginner-friendly financial education web app (Flask + vanilla JS). Specs live in `docs/`.
V2 is an overhaul of [V1](https://github.com/Eman12211e/beginner-friendly-finance-app) (imported at `2eb7701`).

## Zero-cost development mode (on by default)

While `ZERO_COST_MODE` is not `0`, the app cannot make any paid or metered request: the Anthropic, Finnhub, FMP
and Hugging Face keys are ignored, market data is demo data, and the cache warmup is off. V1 features fall back the
way they already do without keys (fixed explanations, chat shows "not available"). Tests also block all network calls.

## Setup (Windows PowerShell)

Python 3.12 (`.python-version`). Keep the project in a short folder path such as `C:\Users\you\finance-app-v2`: one
runtime package (`anthropic`) has very long file names, and without Windows long-path support its install fails in a
deeply nested folder.

```powershell
py -3.12 -m venv venv
venv\Scripts\python -m pip install -r requirements-dev.lock   # exact versions of every package (app + tests)
copy .env.example .env   # optional; the app runs without it, in zero-cost demo mode
```

| File | What it is |
|---|---|
| `requirements.txt` / `requirements.lock` | Runtime: what the app imports / every package pinned, transitive ones included |
| `requirements-dev.txt` / `requirements-dev.lock` | Runtime plus pytest (development and tests) |
| `requirements-build.txt` | Optional: yfinance, only for `scripts/build_demo_data.py` |
| `requirements-sentiment.txt` | Optional: the local FinBERT Sentiment Explorer |

To run the app without the test tools, install `requirements.lock` instead. The locks are `pip freeze` output of clean
installs; regenerate them the same way after an intended version change.

## Run

```powershell
venv\Scripts\python app.py      # development server, http://127.0.0.1:5000
```

## Tests

```powershell
venv\Scripts\python -m pytest
```

**Every check, from scratch** (a fresh virtual environment from `requirements-dev.lock`, pytest in zero-cost mode, then
each browser suite on its own; needs Node 22+ and Edge or Chrome; about 15 minutes; exits non-zero if anything
fails):

```powershell
powershell -File scripts\check_all.ps1 check-all-out      # Windows
bash scripts/check_all.sh check-all-out                   # Git Bash, macOS or Linux
```

Logs and screenshots go to `check-all-out/` (gitignored). `CHECK_SUITES="backtest workflows"` runs only those suites.

**CI:** `.github/workflows/ci.yml` runs `scripts/check_all.sh` on a clean GitHub-hosted Ubuntu runner (Python 3.12,
Node 22, Chrome), with no secrets and read-only permissions, and keeps the logs as an artifact. It runs only once the
repository is pushed with that file; until then CI results do not exist, and local `check_all` runs are the
implementer's own, not independent verification.

## Scripts

```powershell
venv\Scripts\python scripts\check_endpoints.py   # checks provider endpoints; rewrites data/endpoint_check.json only if one was checked
venv\Scripts\python scripts\build_demo_data.py   # rebuilds data/demo_stocks.json from yfinance (needs requirements-build.txt)
```

## AI Strategy Comparison Lab

The "AI Comparison Lab" tab shows six models side by side (Qwen, Kimi, DeepSeek, GPT-OSS and GLM through Hugging Face
Inference Providers, and Claude through the Anthropic API). All six get the same evidence, scenario, prompt and output
schema, and Python checks every output the same way: citations must exist, every number must appear in the cited
evidence, and advice or prediction language is withheld and counted.

**Right now every panel is SIMULATED.** The panels come from deterministic test stand-ins that each trip one validator,
rotating across models by scenario. They are not model output, scores or rankings.

Model ids, providers, prices and licenses live in `data/lab_models.json` (all `provisional`). To check them against the
public Hugging Face listing (free, no token, no inference):

```powershell
venv\Scripts\python scripts\check_lab_models.py
```

### Activating live inference (not approved yet)

Live calls stay refused until **all** of these are true, and the comparison refuses the whole run otherwise:

1. `ZERO_COST_MODE=0` and `LAB_LIVE_ENABLED=1` in `.env`
2. `LAB_DAILY_BUDGET_USD` above `0` (default `0`)
3. `HF_TOKEN` and/or `ANTHROPIC_API_KEY` set in `.env` (never committed)
4. each model's `status` changed to `confirmed` in `data/lab_models.json` after checking it
5. the request sends `"live": true` and `"confirm_live": true`

Before each call the worst-case cost (estimated input plus `LAB_MAX_TOKENS` output at the listed price) is reserved in
`data/lab_spend.json` (gitignored), then corrected to the actual usage. A run that could pass the daily budget is refused.

## Understand Before You Sign

Plain-English guides to a brokerage account agreement, Form CRS, a margin agreement, Form W-9 and identity
verification. Each passage is labelled as official government text, a brief quote from a real firm's Form CRS
(Charles Schwab, SEC-hosted copy), a summary of a FINRA or SIPC source, or a fictional example. Content lives in
`data/documents/*.json`; nothing is generated by AI and the app never asks for personal information.

To re-check quoted wording against the live HTML sources (free, no keys; PDF sources are listed for a manual check):

```powershell
venv\Scripts\python scripts\check_document_sources.py
```

## Compare Brokerages

The "Compare Brokerages" tab shows 2 to 4 firms side by side (stacked cards on phones) for the topics you pick, with
each fact's source, effective date and check date, and labels for source-checked, owner-checked, Unknown and
"Depends on plan" information. Optional filters show which firms meet a condition without ranking them.

### Data and API

Dated, source-backed facts about brokerage firms in `data/brokerages/*.json`, with the comparison criteria in
`data/brokerage_criteria.json`. Each fact cites its source (the firm's Form CRS hosted by FINRA, or the firm's own
pricing pages), a short quote and the date it was verified; anything not verified is shown as Unknown. Firms are
listed alphabetically and never ranked; promotions are not shown. It covers Charles Schwab, Fidelity, Interactive
Brokers and Robinhood. E*TRADE is excluded until its account-opening entity is verified.

To re-check the facts against their sources (free; sites that refuse automated requests are listed for a manual check):

```powershell
venv\Scripts\python scripts\check_brokerage_sources.py
```

When a fact changes, update it, its `verified_on` date and the firm's `audit` list.

### Adding a fact you checked in a browser

Some sites (for example schwab.com) refuse automated requests. To fill an Unknown field by hand:

```powershell
venv\Scripts\python scripts\check_brokerage_sources.py --checklist   # each open field, the page to open, what to verify
```

Open the official page yourself, then replace the Unknown fact in `data/brokerages/<firm>.json` with:
`"kind": "firm_terms"`, `"method": "owner_check"`, `"verified_by"` (who checked), `"source"` (a key in `sources`
with the page URL and, if the document shows one, its `effective` date), `"location"`, `"quote"` (the exact wording,
40 words at most), `"value"`, `"display"` and `"verified_on"`. Add a line to the firm's `audit` list. The app labels
these as checked by the app owner, not as a regulatory certification. Never enter personal or account details.

## Paper Trading Lab (backend, milestone P1)

A self-contained practice simulator: $10,000 of fictional cash, cash-only and long-only, whole-share market orders,
replaying a fixed synthetic daily market chosen on the start screen: `synthetic-b` (default; 12 fictional tickers in 6
sectors over 250 days, with sector-correlated moves, a scripted earnings gap and a scripted drawdown) or the original
`synthetic-a` (`SAMPLE-A` and `SAMPLE-B`, 120 days). Both live in `data/paper/scenarios/` and are rebuilt by
`scripts/build_synthetic_scenario.py` from fixed seeds; the same seed always gives the same file. Orders placed after a simulated
close fill at the next simulated day's opening price. It leaves out real-world fees, spreads, slippage and market
impact, and never connects to a brokerage or market data service. The "Practice Trading" tab (milestone P2) uses it: preview, confirm or cancel practice orders, step through
simulated days, and see holdings, gains and losses and history. The signed session and the optional practice journal
are kept in the browser's localStorage; journal notes are never sent to the server. Charts come in milestone P3.

The browser keeps only a practice log signed by the server (HMAC); every request re-derives cash, positions and
profit/loss from that log, so balances sent by a browser are never trusted. Set `PAPER_STATE_SECRET` (at least 32 characters), or a
random key is created at `data/paper_state.key` (gitignored) on first use and reused after restarts; changing or
deleting the key ends existing practice sessions.

Third-party code: the practice price chart (P3) uses TradingView Lightweight Charts 5.2.1, vendored unmodified in
`static/vendor/lightweight-charts/` with its Apache-2.0 LICENSE and NOTICE. Nothing is loaded from a CDN.

## Optional: Sentiment Explorer (local FinBERT)

Off by default. It classifies fixed, fictional example statements with the Hugging Face model
`ProsusAI/finbert`, run locally on the CPU. The core app and tests do not need it.

```powershell
venv\Scripts\python -m pip install -r requirements-sentiment.txt   # about 155 MB download
venv\Scripts\python scripts\download_sentiment_model.py            # about 438 MB, once, to the Hugging Face cache
$env:SENTIMENT_ENABLED="1"; venv\Scripts\python app.py
```

FinBERT weights are licensed CC BY-NC-SA 4.0 (non-commercial use only). They are stored in the
Hugging Face cache outside this repository and must never be committed. If the packages or weights
are missing, the explorer reports "Model unavailable" and shows no sentiment.
