# WORKFLOW.md — Final Build Workflow (corrected after audit)

> This is the one page to keep open. Put it in `docs/`. Every step below is a copy-paste of a prompt file
> or a short human action. Deadline **8:45 PM PST**. Feature freeze **7:30 PM**.

---

## 0. The kit

| Document (→ `docs/`) | Purpose |
|---|---|
| `ARCHITECTURE.md` | Structure, ownership, interfaces, locked decisions, **Wave 4 added** |
| `API_CONTRACT.md` | Every endpoint, JSON shape, demo-data schema, frontend module contract |
| `AI_RULES.md` | Prompts, validation checks, fallback text, all static copy |
| `DEMO_SCRIPT.md` | Run commands, pre-demo checklist, 12-step click path, recovery, judge Q&A |
| `WORKFLOW.md` | This file |

| Agent prompt (→ paste into one Sonnet agent each) | Wave |
|---|---|
| `PROMPT_W0_SCAFFOLD.md` | 0 |
| `PROMPT_A_DATA_BACKEND.md` · `PROMPT_B_FRONTEND.md` · `PROMPT_C_AI.md` | 1 (parallel) |
| `PROMPT_I_INTEGRATOR.md` + A/B/C reports, marked **"Wave 2"** | 2 |
| `PROMPT_D_FEATURES.md` · `PROMPT_E_LIVE_DATA.md` | 3 (parallel) |
| `PROMPT_I_INTEGRATOR.md` + D/E reports, marked **"Wave 4"** | 4 |

Agents only know what is in `docs/` and their prompt. **Always use the latest versions of the docs.**

---

## 1. Audit fixes applied (what changed since approval)

| # | Fix | Where |
|---|---|---|
| 1 | **Wave 4 checkpoint (Agent I2)** added. D and E now get a full regression and end-to-end pass in both demo and live mode. | `ARCHITECTURE.md` §3; `PROMPT_I_INTEGRATOR.md` (reusable for Wave 2 and Wave 4, checks 14–17 added) |
| 2 | **Provenance rule.** Memoized demo data is always reported as `"demo"`, never `"cache"`. Only live-origin cache hits say `"cache"`. | `ARCHITECTURE.md` §4; `API_CONTRACT.md` §1; A's cache test rewritten; E's fallback test extended |
| 3 | `get_financials()` dict documented to carry `ticker`, `name`, `is_etf`. | `ARCHITECTURE.md` §5; `PROMPT_A` §2.3 |
| 4 | Live mapping for `dividend_yield` (Finnhub `/stock/metric`, E verifies) and `expense_ratio` (always `null` live). | `API_CONTRACT.md` §4; `PROMPT_E` §2.2b |
| 5 | Null plain-string fields (`name`, `sector`, `exchange`, `currency`) defined; UI shows the ticker for a null name. | `API_CONTRACT.md` §3.2; `PROMPT_B` §2.6 |
| 6 | C2 number-format false positives: **not changed**; measure in rehearsal (step 7 below). | — |
| 7 | `InvalidRequest` (`INVALID_REQUEST`, 400) added to the error classes. | `ARCHITECTURE.md` §5 |
| 8 | Missing EPS comparison: `headline.available: false`, `headline` explain is `null` (no fallback). Test T15. | `AI_RULES.md` §5.1, §7, §8; `API_CONTRACT.md` §3.3; `PROMPT_C` |
| 9 | Dividend: known non-payer gets the "does not pay" explanation; unknown (`pays_dividend: null`) gets `null`. Tests T16 + A's dividend test. | `AI_RULES.md` §5.1, §7, §8; `API_CONTRACT.md` §3.3; `PROMPT_A`, `PROMPT_C` |
| 10 | Wave 4 done criteria say 17 checks (check 17 live only). | `ARCHITECTURE.md` §3; `PROMPT_I_INTEGRATOR.md` §6 |

---

## 2. The workflow

```
 Human: docs/ + .env
        │
        ▼
 ┌─────────────┐
 │  Wave 0: W0 │  Scaffold · shared helpers · stubs · endpoint check · demo data
 └──────┬──────┘
        │ commit  ─── Human gate 1: check endpoint results + demo-data gaps
        ▼
 ┌──────────┬──────────┬──────────┐
 │ A: Data  │ B: Front │ C: AI    │  Wave 1, parallel, no shared files
 └────┬─────┴────┬─────┴────┬─────┘
      └──── 3 commits + 3 reports ────┐
                                      ▼
                             ┌────────────────┐
                             │  Wave 2: I     │  Integrate A+B+C · 13-step check · cleanup
                             └───────┬────────┘
                                     │ commit ─── Human gate 2: click the core flow yourself
                                     ▼
                          ┌──────────────┬──────────────┐
                          │ D: Features  │ E: Live Data │  Wave 3, parallel
                          └──────┬───────┴──────┬───────┘
                                 └── 2 commits + 2 reports ──┐
                                                             ▼
                                                    ┌────────────────┐
                                                    │  Wave 4: I2    │  Regression · 17-step check in demo AND live · git tag demo-ready
                                                    └───────┬────────┘
                                                            ▼
                                        7:30 FREEZE → rehearse ×3 → fix bugs only → submit by 8:45
```

---

## 3. Step by step

### Step 0 — Human setup (5 min)
1. Create `financial-education-mvp/docs/` and copy in the 5 documents.
2. Create `.env` with `ANTHROPIC_API_KEY`, `FINNHUB_API_KEY`, `FMP_API_KEY`, `DATA_MODE=demo`, `WARM_CACHE=0`. No agent ever handles the keys.

### Wave 0 — W0 Scaffold (~30 min)
- Paste `PROMPT_W0_SCAFFOLD.md`.
- **Exit:** app boots with no `.env` · `/api/health` works · `pytest` green · 9 endpoint result lines · `demo_stocks.json` generated by script · commit.

**Human gate 1:** read report sections 3 (endpoint check) and 4 (demo-data gaps).
- Any FMP endpoint `FAIL` → tell Agent A and E in their prompts: that field is `null` in live mode.
- Any demo field `null` for a demo ticker → acceptable; it will show "Data not available". Note it for the presentation.

### Wave 1 — A, B, C in parallel (~90 min)
- Paste the three prompts into three agents at the same time.
- **Exit per agent:** its tests pass · one commit · final report with a "changes needed in files you do not own" section.
- B can work with `?mock=1` before A finishes. C's tests never call the real Claude API.

### Wave 2 — I Integrator (~45 min)
- Paste `PROMPT_I_INTEGRATOR.md`. At the bottom write **"Wave 2"** and paste A, B, and C's reports.
- **Exit:** `pytest` green · 13-step end-to-end check passes in demo mode · mock mode deleted · `INTEGRATION_NOTES.md` written · commit.
- If I reports "two fixes failed, stopping": hand that one bug to your Codex/ChatGPT debugger using the bug template, with `INTEGRATION_NOTES.md` attached.

**Human gate 2:** open the app yourself. Onboard → AAPL → VOO → chat "What is EPS?" → chat "Should I buy this?". If this works, the demo already exists. Everything after is an upgrade.

### Wave 3 — D, E in parallel (~60 min)
- Paste `PROMPT_D_FEATURES.md` and `PROMPT_E_LIVE_DATA.md` into two agents.
- **Exit D:** alerts and checklist work · every alert carries the simulated label · tests pass · commit.
- **Exit E:** live-vs-demo sanity table filled · fallback tests pass · wrong-key test passes · warmup under 1 s per ticker · commit.
- E's report section 6 lists which fields are `null` in live mode. Decide then: present in live or demo mode (`DEMO_SCRIPT.md` §1).

### Wave 4 — I2 Final Integrator (~30 min) ← new
- Paste `PROMPT_I_INTEGRATOR.md`. At the bottom write **"Wave 4"** and paste D and E's reports.
- **Exit:** `pytest` green across all suites · 17-step check passes in **demo** and in **live + warm cache** · `INTEGRATION_NOTES.md` has a "Wave 4" section · commit · **`git tag demo-ready`**.

### 7:30 PM — Feature freeze
- No new code. Bug fixes only, each verified against `pytest` and the click path.
- Screen-record one full run of `DEMO_SCRIPT.md` §3. This is the last-resort backup.

### 7:30–8:15 — Rehearse (3 runs)
- Run the click path in your chosen mode. Time it (target ~4 min).
- **Measure C2:** in each run, ask the chat two number questions ("What is Apple's revenue?", "What is KO's dividend?"). If replies are replaced by the "I can only use numbers that are shown in the app" text more than once in 6 tries, have your debugger make the C2 comparison format-tolerant (same number, different formatting). Do not remove the check.
- Anything broken → `git checkout demo-ready` and present from the tag.

### 8:15–8:45 — Buffer and submit
- Submit early. Keep the app running for the presentation.

---

## 4. Timeline (from 2:00 PM)

| Time | Wave | Human action |
|---|---|---|
| 2:00–2:30 | 0 | Gate 1 |
| 2:30–4:00 | 1 (A, B, C) | Wait; answer agent questions |
| 4:00–4:45 | 2 (I) | Gate 2: click the core flow |
| 4:45–5:45 | 3 (D, E) | Pick live or demo mode |
| 5:45–6:15 | 4 (I2) | Confirm `demo-ready` tag |
| 6:15–7:30 | Debug and polish | Codex/ChatGPT on any open bugs |
| **7:30** | **Freeze** | Screen recording |
| 7:30–8:15 | Rehearsal | 3 runs, C2 measurement |
| 8:15–8:45 | Buffer | Submit |

About 75 minutes of slack sits between Wave 4 and the freeze. If a wave runs long, it comes out of that slack, not out of rehearsal.

---

## 5. Rules that never bend

1. One owner per file. Agents report cross-file needs; they do not make them.
2. The docs win over the code. If a doc is wrong, the human changes the doc, not the agent.
3. Python writes every number. Claude writes only words, and never sees the numbers for earnings.
4. Missing data shows "Data not available". Nothing is estimated, borrowed, or filled.
5. Demo data is always labeled demo, even when served from memory.
6. Two failed fixes on one bug → stop, write it up, hand it to a human.
7. After 7:30, bug fixes only.
