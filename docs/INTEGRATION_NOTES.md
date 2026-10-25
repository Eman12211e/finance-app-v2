# INTEGRATION_NOTES.md

Owner: Agent I (Integrator). One entry per change: `- [file] what was wrong → what changed → how verified`.

## Wave 2 (Agent I)

Baseline before any change: `pytest` 75 passed. Commits present: W0 `607f726`, A `c090391`, C `a949cda`, B `4a3f17e` (plus `d059ebb` test-key isolation).

### Changes requested in agent reports
- [static/js/chat.js] Send button shrank in the narrow chat column and its label wrapped to "Sen / d" (Agent B report) → added `#chat-root .chat-row button{flex:none}` to the injected chat styles → headless Edge: button renders on one line (32 px high), screenshot checked.
- [tests/test_scaffold.py] No regression test guarded the conftest.py key isolation (recommended in the `d059ebb` report) → added `test_tests_never_see_real_api_keys` (all three keys `""`, `DATA_MODE` demo, `WARM_CACHE` off) → `pytest` 76 passed.

### End-to-end fixes
- [static/js/chat.js] Starter chips stayed visible after the first message: the `.chat-starters{display:flex}` rule overrode the `hidden` attribute, contrary to PROMPT_C §2.4 ("shown when empty") → added `#chat-root .chat-starters[hidden]{display:none}` → headless Edge: chips visible before the first message, hidden after.

### Cleanup
- [static/js/mock_responses.js] Dev-only mock data → deleted → `/static/js/mock_responses.js` returns 404.
- [templates/index.html] `?mock=1` inline loader → removed → `/?mock=1` loads no mocks (`window.MOCK_RESPONSES` undefined, no banner).
- [static/js/api.js] `window.MOCK_RESPONSES` branch in `request()` → removed → all calls go through `fetch`; e2e checks 1–13 pass.
- [static/css/style.css] Unused `.mock-banner` rule → removed → no remaining `mock` references in `static/` or `templates/`.
- `console.log` debug lines: none found. Dead or commented-out code: none found beyond the mock path.

### Verification
- `pytest`: 76 passed.
- `node --check`: all 6 files in `static/js/` pass.
- Static checks: `fetch(` only in `api.js` · no `innerHTML` · no key, `token=` or `apikey=` value in `static/` or `templates/` · `anthropic` imported only in `services/ai_service.py` · provider `requests` calls only in `finnhub_client.py`, `fmp_client.py` and `scripts/` · `yfinance` imported only in `scripts/build_demo_data.py` · AI_RULES §9 copy present word for word (Agent D copy pending Wave 3).
- End-to-end §3 in headless Edge (disposable profile, `DATA_MODE=demo`, all API keys blanked for the server process): checks 1–6 and 9–13 PASS; 7 and 8 NOT RUN (need real Claude replies; Anthropic key intentionally absent); 12 verified as the no-key case. Server log shows no Finnhub, FMP or Anthropic calls.

### Open items (not changed)
- Real Claude output (check 3 AI text, checks 7 and 8) is unverified until an Anthropic key is used.
- PROMPT_B_FRONTEND §2.3 names the mock ETF `EXMPLF` (6 letters), which the contract's 1–5 letter ticker rule rejects. The mock is now deleted, so this matters only for the doc.

## Post-integration verification (2026-10-24)

The Wave 2 results above stand as recorded: the Anthropic key was absent during those integration tests. A key was added to `.env` afterwards, and real Claude output was checked with a hard limit of 2 calls per run (`DATA_MODE=demo`, `WARM_CACHE=0`, Finnhub and FMP disabled, SDK retries off).

- [services/ai_service.py] First live run (2 calls): both replies were cut off. Claude Sonnet 5.5 thinks by default when `thinking` is not set, and thinking spends `max_tokens` (300 chat / 900 earnings). Earnings JSON stopped mid-string (V1 → full fallback); chat returned no text (`AI_UNAVAILABLE`). Safe outcomes, but no Claude text reached the user → `_call_claude` now sends `thinking={"type": "between_tools"}` (thinking off; valid at the default effort, no effort setting is sent) and logs `stop_reason`, `output_tokens` and `max_tokens` only (WARNING when `stop_reason=max_tokens`) → mocked tests `test_call_claude_turns_thinking_off_and_logs_stop_reason` and `test_truncated_replies_stay_safe`; `pytest` 78 passed.
- Second live run (2 calls, after the fix):
  - AAPL earnings, age 25–34, medium risk: HTTP 200, `explanation_source=ai`, `stop_reason=end_turn`, 412 of 900 output tokens. One validation replacement: `V4 banned term in field=dividend` ("guaranteed" matched `guarantee\w*`), so dividend used the fallback sentence. All other fields were Claude text with no digits, no banned terms and no advice.
  - Chat "What is EPS?", same profile, no company context: HTTP 200, `stop_reason=end_turn`, 101 of 300 output tokens. A correct educational definition with no numbers or advice; C2 and C3 made no replacement.

### Open items
- The chat reply had five sentences; CHAT_SYSTEM_PROMPT asks for 2 or 3. Not a safety issue, and no Python check covers chat length (AI_RULES §6.3 has C1–C3 only). The prompt is unchanged for now.
- Two live samples confirm the fix works; they do not measure how often validation replaces Claude text. That is the rehearsal measurement in WORKFLOW.md step 7.

## Wave 4 (Agent I2)

Start: commit `43a2a00`, clean tree. `pytest` 100 passed before and after. `node --check` passes for all 8 files in `static/js/`. Agent D and E reports listed no changes needed in files they do not own.

### Changes
- None. No integration defect was found, so no code changed in Wave 4.

### Verification method
- Headless Edge with a disposable profile and localhost-only debugging, against a test launcher on port 5055 (port 5000 was in use by a separate app instance and was not touched).
- The launcher runs the real app in `DATA_MODE=demo`, `WARM_CACHE=0`, with Finnhub and FMP keys blanked. For the AI checks it replaces `ai_service._call_claude` with scripted replies and blocks the real Anthropic client, so every validator (V1–V7, C1–C3) ran end to end with no network call. Check 12 used a second launch with no Anthropic key.
- External calls in Wave 4: 0 (Anthropic 0, Finnhub 0, FMP 0). The real Anthropic client was never constructed.

### End-to-end results (PROMPT_I_INTEGRATOR §3, demo mode)
- PASS 1–16. Highlights: AAPL numbers match `demo_stocks.json` (revenue 109417000000, EPS 2.02 vs 1.89243); `explanation_source=ai` with scripted Claude text; a Claude field containing a digit was replaced by its fallback (V3); "You should buy it now." was replaced by the advice fallback and the checklist link appeared (C3 + C1); an invented "$999.99B" chat reply was replaced (C2); chat carried `source=demo`; server stop shows "Could not reach the server." and recovers; one toast with "Simulated alert: demo only", badge 9 cleared on open; removing KO removed its 2 alerts; checklist opens from the header and the chat link, Escape closes and returns focus; 380 px has no horizontal overflow.
- PASS keyboard: Tab order profile chip → alerts bell → "Before you buy" → watchlist, each with a visible focus outline; Enter activates a ticker button and sends chat.
- PASS static checks: `fetch(` only in `api.js`; no `innerHTML`; no key, `token=` or `apikey=` value in `static/` or `templates/`; `anthropic` only in `ai_service.py`; provider `requests` only in the two clients and `scripts/`; `yfinance` only in `build_demo_data.py`; all AI_RULES §9 copy, including Agent D's alert label and checklist text, present word for word.
- NOT RUN 17 (live mode): real provider calls were not approved for this wave. Evidence instead is Agent E's live run at `43a2a00` (prices equal to demo, market cap within 0.2%, revenue and net income identical for the same quarter, `live` → `cache` provenance with the original `as_of`, demo fallback never reported as `cache`, wrong-key fallback with no crash and no key in the log).

### Provider differences reviewed (all labels correct; no live/demo mixing)
- AAPL EPS: live (Finnhub) 1.91 vs 1.9271 → "Below"; demo (Yahoo) 2.02 vs 1.89243 → "Above". Each pair is one record of one provider; the headline differs by mode.
- NVDA: Finnhub labels the EPS quarter "Sep 30, 2026"; the matching income statement is dated Jul 26, 2026. EPS values match demo.
- `dividend_yield` is null in live mode (Finnhub metric unreliable, e.g. NVDA 0.03% vs 0.47%); `expense_ratio` is null in live mode by contract; VOO name, exchange and sector are null live (no Finnhub profile for the ETF). All show "Data not available".
- A demo fallback stays cached for its TTL (24 h for financials), correctly labelled "Demo data".

### DEMO_SCRIPT.md accuracy (doc not changed; planner decision)
- §1 primary mode is live. In live mode, step 4's "EPS vs. analyst estimate: Above" is wrong for AAPL (live shows "Below"), and dividend yield shows "Data not available" for every ticker.
- Step 3 says "This is live data from Finnhub and FMP." In demo mode the badge reads "Demo data (as of Oct 24, 2026)", so the line needs the demo wording.
- Step 5 and the first judge answer say Claude never receives the numbers. That is true for earnings explanations; chat does receive the on-screen display strings and may repeat only those (C2 checks this).
- Step 9 says answers are two or three sentences; the one live chat sample had five (prompt-level, not enforced in Python).
- Run commands should use the project venv (`venv\Scripts\python app.py`). With `WARM_CACHE=1` and a real key, warmup makes up to 5 paid Claude calls for the default profile.

### Post-Wave 4: risk-specific stock questions (approved enhancement)
- [services/prompts.py, services/ai_service.py] All profiles saw the same three stock questions, and Claude's questions replaced them when the call succeeded → added `STOCK_QUESTIONS` (approved low/medium/high sets) and `_fixed_questions()`; stock questions now always follow `profile.risk`, for Claude success, field fallback and full fallback. ETF questions and V7 for ETFs are unchanged. No extra Claude call (the AI cache key already includes risk) → `pytest` 107 passed (T17 for all three risks, route test with no key and no Claude call, ETF regression).
- [docs/AI_RULES.md, docs/API_CONTRACT.md] V7, section 7, T1 and new T17 updated to the deterministic policy; API_CONTRACT §3.3 notes the stock-question source. The 3-question shape is unchanged.
- Debt and cash flow: the demo data and contract carry revenue, net income, cash and equivalents, EPS, dividend and next earnings date only. FMP's balance sheet response has debt fields but the app does not read them, and no cash-flow endpoint is used. The debt and cash-flow questions are conceptual; no figures were added.
- Risk education panel (Goldman Sachs source): first on hold. The one approved download of the source URL returned HTTP 200 with a 431-byte HTML loader page, not the PDF, so the attribution could not be verified here. The user then confirmed the source independently (Semester with Goldman Sachs 2025, Session 5, slide 24, plus the Session 5 one-pager) and approved the panel copy.

### Post-Wave 4: risk education panel (approved enhancement)
- [templates/index.html, static/js/risk_education.js, static/js/app.js, static/css/style.css] Added a static "Understanding risk tolerance" panel in `#risk-education` at the bottom of the watchlist sidebar → `window.RiskEducation.init()` renders the three approved levels (Low — Conservative, Medium — Moderate, High — Aggressive), marks the saved `profile.risk` as "Your selection" (`aria-current`), and re-renders on `app:profile-changed`. Prewritten text only: no AI, no `fetch`, no figures. Both official 2025 source links are shown (slides, then one-pager) because the slides URL served a loader page to a plain download; each opens in a new tab with `rel="noopener noreferrer"`. Attribution lines exactly as approved, including "Static educational content — not AI-generated." and "Not affiliated with or endorsed by Goldman Sachs." → `tests/test_risk_education.py` (placement, script order, exact copy, links, no network, no figures); headless Edge with every key blank: all three levels, switch without reload with no panel requests, links focusable, attribution visible, 380 px fit, zero external requests; Wave 4 regression unchanged (16 PASS, 1 NOT RUN); `pytest` 110 passed.
- [docs/API_CONTRACT.md] §6: `risk_education.js` added to the script order before `app.js`, `window.RiskEducation` global, `#risk-education` container, and RiskEducation as an `app:profile-changed` listener.

### Post-Wave 4: Brokerage & Investing Accounts 101 (approved enhancement)
- [templates/index.html, static/js/accounts.js, static/js/app.js, static/css/style.css] Added a "Learn about accounts" header button that opens a static modal: 13 commonly encountered account types in 4 categories (Everyday brokerage 4, Family and estate 2, Retirement 4, Education and healthcare 3), each an accordion button (`aria-expanded`, `aria-controls`, region panel) with How it works / Typical use / Watch out for (48–63 words) and official source links. Intro states these are not 13 exclusive official categories and that they overlap. No AI, no `fetch`, no contribution limits, ages or other figures, no recommendations. Escape, Close and backdrop close it; focus moves in, is trapped with Tab, and returns to the button → `tests/test_accounts.py` (13 entries and categories, length, verified official links only, no figures or advice, intro and notice, placement); headless Edge with every key blank: open, click and keyboard (Enter/Space) toggling, focus trap, three close paths with focus return, 21 links on investor.gov / finra.org / irs.gov, 380 px fit, zero external requests; Wave 4 regression and risk panel regression unchanged; `pytest` 116 passed.
- Sources: 17 official URLs, each confirmed by its real page title (Investor.gov returns 200 with a generic "Glossary" title for missing pages, so status alone was not trusted; IRS and FINRA return real 404s). The joint-account entry has no joint-specific official page among those checked; it links FINRA's general Brokerage Accounts page and makes no claim beyond it.
- [docs/API_CONTRACT.md] §6: `accounts.js` in the script order before `app.js`, `window.Accounts` global, `#accounts-open` button and `#accounts-root` container.

### Post-Wave 4: optional Sentiment Explorer (local FinBERT) (approved enhancement)
- Feasibility: `ProsusAI/finbert` is public and not gated; `text-classification`; labels positive/negative/neutral; `model.safetensors` 438 MB; weights CC BY-NC-SA 4.0 (training data CC BY-NC-SA 3.0). Hosted `hf-inference` was live, but local CPU inference was chosen: no network or token at demo time.
- [services/sentiment_service.py, routes/sentiment.py, data/sentiment_statements.json, config.py, app.py] Added the optional feature, off by default (`SENTIMENT_ENABLED=0`). The service is the only file that imports `transformers`, loads lazily with `local_files_only=True`, never raises, and returns `inference: "unavailable"` with no label or scores whenever the model cannot run. Six fictional example statements, no figures, no free text. Only real model results are cached → `tests/test_sentiment.py` (disabled mode, model vs unavailable, load failure not retried, inference failure, unexpected labels, caching, bad ids, fictional statements with no figures, transformers never imported in normal runs, no Claude call, page markup).
- [static/js/sentiment.js, static/js/api.js (B), static/js/app.js, templates/index.html (B), static/css/style.css (B)] Header button hidden unless the server reports `enabled: true`; accessible modal (Escape, Close, backdrop, focus trap and return) with the disclaimer, the fictional-statements note, label plus all three scores, a provenance line, attribution and license links. `api.js` gained `getSentimentStatements` and `postSentiment` because `fetch(` stays in that file only.
- [requirements-sentiment.txt, scripts/download_sentiment_model.py, .gitignore, .env.example (W0), README.md (W0), tests/conftest.py (W0)] Optional pinned packages (not installed), a one-time download script (not run), weights and cache paths ignored by git, `SENTIMENT_ENABLED=0` in the example env and forced off in tests.
- [docs/ARCHITECTURE.md] Ownership line for `sentiment_service.py`, the optional-dependency exception, and a note that decision 6 (no news) still holds.

### Open items
- Real Claude output beyond the two earlier samples is unverified; measure during rehearsal (WORKFLOW.md step 7).
- Earnings alerts use saved dates (KO Oct 27, MSFT Oct 28, AAPL Nov 2, NVDA Nov 17, 2026); after a date passes the alert still says "expected" until demo data is rebuilt.
