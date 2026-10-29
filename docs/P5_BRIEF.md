# P5 — Strategy Experimentation and Backtesting: approved brief

Owner approval: 2026-10-29, decisions D1–D12 accepted as recommended (table at the end). Base: `dev/v2` at `e929096`
(P4 step 8). Progress and checks are logged in `docs/P5_PROGRESS.md` once implementation starts.

Inputs read: `docs/P4_BRIEF.md`, `docs/P4_PROGRESS.md`, `docs/P3_PROGRESS.md`, `docs/P2.5_PROGRESS.md`,
`docs/API_CONTRACT.md`, `docs/ARCHITECTURE.md`, `services/paper_engine.py`, `services/paper_market.py`,
`services/indicators.py`, `routes/analysis.py`, `data/paper/scenarios/*.json`, `scripts/build_synthetic_scenario.py`,
`scripts/qa/`. Roadmap v3 itself is not in the repository; see "Roadmap v3 check" at the end.

## 1. Scope and educational objectives

A learner picks one synthetic ticker and one preset rule, runs it over the simulated days they have already reached in
Practice Trading, and compares the result with simply buying and holding the same ticker over the same days. The
point is to learn how a rule-based strategy is tested and why its results are fragile, not to find a "winning" rule.

The learner should come away able to say:

- what a backtest is: a rule replayed on past prices with fixed, written-down assumptions;
- why each assumption (when orders fill, costs, whole shares, warm-up) changes the answer;
- why a rule that ended higher than buy-and-hold in one stretch can end lower in another (Section 3.8);
- what total return, maximum drawdown and volatility measure, and what they cannot tell you.

**In scope:** three presets (Section 2), daily bars only, one ticker per run, long-only, the existing synthetic
scenarios, a read-only endpoint, a value chart with entry and exit markers, plain explanations, offline tests.

**Out of scope:** real or live market data, real brokerage access, real orders, predictions or forecasts, parameter
optimisation or free-entry parameters, short selling, leverage, margin, multi-ticker portfolios, weekly backtests,
AI-written text, saving or sharing results, any change to the Practice Trading engine.

Every result is labelled **Simulated: hypothetical results on synthetic prices**. Tests reject advice and prediction
wording (Section 4, Wording rules).

## 2. Strategy presets

All signals are computed from **daily closes up to and including the decision day**, using the P4 functions in
`services/indicators.py` (unrounded values). Presets only: no periods or thresholds can be typed (as P4 decision 2).
Exact start and entry rules are in Section 3.2.

| Preset | Rule | Why it is here |
|---|---|---|
| **Buy and hold** (benchmark) | Buy once on the first fill day; never sell. | The baseline every rule is compared with. Shown with every run, never chosen on its own. |
| **SMA crossover 20 / 50** | Enter on a cross of SMA 20 above SMA 50; exit on a cross back below. | Trend-following; reuses the SMA 20 / 50 presets learners met in P4. |
| **RSI 14 threshold 30 / 70** | While out: enter when RSI 14 closes below 30. While in: exit when RSI 14 closes above 70. | Mean-reversion, the opposite idea. Reuses the RSI 14 preset and its 30 / 70 guides. |

**EMA crossover is left out of the MVP (D1).** EMA 12 / 26 crossing is the same event as the MACD line crossing zero,
which P4 already explains, and it is another "fast average crosses slow average" rule like SMA 20 / 50. A learner
comparing two near-identical trend rules is drawn into picking the "better" one, the habit this feature should
discourage. It can be added later as a preset without changing the engine.

## 3. Backtesting conventions

These are written into the results panel ("How this test works") as well as the code.

### 3.1 Day numbering

The code and the API use **zero-based day indices**; the interface shows **trading-day numbers** (index + 1), as
Practice Trading already does ("Day 70 of 250" is index 69). Every rule below gives both.

| Point | Index | Shown as |
|---|---|---|
| SMA 50 first has a value (needs 50 closes: indices 0–49) | 49 | Day 50 |
| **Start day S**: everyone holds $10,000 cash at its close; first decision made at its close | 49 | Day 50 |
| First possible fill (open of the day after S) | 50 | Day 51 |
| First day a crossing can be detected (needs SMA values on two days, 49 and 50) | 50 | Day 51 |
| First possible crossover fill | 51 | Day 52 |
| **Minimum last day L** (S + 20) | 69 | Day 70 |
| Last day of synthetic-a / synthetic-b | 119 / 249 | Day 120 / Day 250 |

"Evaluation days" means `L − S`: the number of daily changes in value, which is also the number of days a fill could
happen. At the minimum, L = 69 gives 20 evaluation days and needs **70 trading days** of history (indices 0–69).

### 3.2 Initial state and entry rules

Every preset and the benchmark start identically: **at the close of day S, all cash ($10,000.00), no shares, no
earlier trades.** Days before S are used only to compute indicators. No position is assumed to exist before S, and no
trade before S is inferred from indicator values (in particular, SMA 20 already being above SMA 50 on day S is not
treated as an earlier entry).

Decisions are made at the close of each day t with S ≤ t ≤ L, from data up to t. A decision on day t fills at the open
of t + 1, so only decisions with t < L can fill.

- **Buy and hold:** on day S it decides to buy; it fills at the open of S + 1 (index 50, Day 51) and holds to L.
- **SMA crossover:** "above" means SMA 20 > SMA 50 (equal counts as not above). A **cross up** on day t means not
  above on t − 1 and above on t; a **cross down** means above on t − 1 and not above on t. Both days need SMA values
  and index 49 is the first with SMA 50, so the first detectable cross is on index 50 (t − 1 = S). While out, a cross
  up enters; while in, a cross down exits. If the averages never cross after S the rule stays in cash for the whole
  window.
- **RSI threshold:** RSI 14 has values from index 14, so it is defined on S. While out, RSI 14 < 30 at the close
  enters; while in, RSI 14 > 70 at the close exits (strict inequalities; exactly 30 or 70 does nothing). If RSI is
  already below 30 on day S, that is a decision made on day S and fills on Day 51, the same first fill day as the
  benchmark; it is not an earlier trade.

All three therefore cover exactly the same days (S to L) from the same starting state, and no preset can fill before
index 50.

### 3.3 Execution timing

- One decision per trading day, after the close of day t, from data up to day t.
- A decision on day t fills at the **opening price of day t + 1**, the Practice Trading rule (`FILL_NOTE`), so learners
  see one convention across the app. The gap between t's close and t + 1's open is shown in the fills list (the
  scripted earnings gap on SYN-TEC2, index 90 / Day 91 of synthetic-b, is a worked example).
- A signal on the last day L cannot fill (no next open) and is listed as "signal on the last day, not acted on".
- At most one fill per day; a position cannot be entered and exited on the same day.

### 3.4 Capital, sizing and the no-borrowing guarantee

- **$10,000.00** of fictional cash (`1_000_000` cents, the Practice Trading starting balance).
- **All in, all out, whole shares (D5):** an entry buys `shares = floor(cash / buy_price)` at the fill price including
  slippage; an exit sells every share held. No partial sizing, no adding to a position, no fractional shares.
- **No borrowing, negative cash or leverage, by construction:**
  - commission is $0 and slippage is inside the integer-cent fill price, so a buy costs exactly
    `shares × buy_price ≤ cash`;
  - if `cash < buy_price` the entry is skipped and listed with a reason ("could not afford one share"); it is only
    reachable in test data;
  - a sell is only possible while holding, and sells exactly the shares held, so shares never go below zero (no
    short selling);
  - there is no margin, no credit and no second position.
  The engine asserts `cash ≥ 0` and `shares ≥ 0` after every fill, and tests check it on every symbol and day.
- Leftover cash (less than one share's price) stays as cash and earns nothing; the results show it. For the dearest
  synthetic ticker, SYN-IND1, which starts near $165, that is under about 1.7% of $10,000.

### 3.5 Transaction costs and slippage (D4)

- Commission: **$0** (commission-free stock trading is the common case and keeps the arithmetic visible).
- Slippage, two presets: **"Example costs"** (the default): each fill is 0.10% worse than the open (a buy pays more, a
  sell receives less). **"No costs"**: fills at the open exactly, as the Practice Trading engine does.
- In integer cents: buy price `ceil(open × 10010 / 10000)`, sell price `floor(open × 9990 / 10000)`. Rounding always
  goes against the trader, so costs are never understated.
- Results show **Costs paid** in dollars, so the effect is visible without a second run.

### 3.6 Final valuation

- Value each day = `cash + shares × close` (integer cents), from the close of S (exactly $10,000.00) to the close of L.
- An open position at the end is **valued at the last close, not sold** (no extra cost charged). The results say
  "still holding N shares at the end, valued at the Day L + 1 close".

### 3.7 No future-data leakage (D6: current session only)

- Bars come only through `paper_engine.market_bars(state)`, which verifies the signed session and stops at the
  session's current day. **L is the current practice day**, so a test never shows a price the learner has not reached
  in Practice Trading.
- Decisions on day t read indicator values at index t, and every indicator function in `services/indicators.py` is
  causal (the value at i uses inputs 0..i).
- A fill on t + 1 uses only t + 1's open; the decision for t + 1 is not made until t + 1 closes.
- Tested by prefix stability and by changing later prices (Section 7).

### 3.8 Earlier and later halves (D7): descriptive only

- The window is also shown as two halves, each run as its own test from the same starting state (Section 3.2, with
  its own S): **earlier half** S to M and **later half** M to L, where `M = S + floor((L − S) / 2)`. Indicators in the
  later half still use every close before M, which is not leakage.
- Shown only when each half has **at least 40 evaluation days** (L − S ≥ 80, so L ≥ index 129, Day 130); otherwise
  "Too short to split". Synthetic-a (last index 119) therefore never shows halves; synthetic-b does from Day 130.
- **This is a description, not validation.** No parameters are fitted (the presets are textbook periods fixed before
  these prices were seen), so neither half is a training set and the later half is **not out-of-sample evidence that
  the rule works**. The halves only show that the same fixed rule can behave very differently in different stretches
  (in synthetic-b the scripted market-wide decline, indices 170–189 / Days 171–190, falls in the later half). The UI
  says so in those words and never labels the halves "in-sample" or "out-of-sample".

### 3.9 Insufficient history

- A test needs **70 trading days** (L ≥ index 69). Below that the endpoint answers `ok: true` with `result: null`,
  `needed_days: 70` and `available_days` (L + 1), and the UI shows "Not enough data: this test needs 70 trading days
  of history; N are available so far." Nothing is estimated.
- A run with no signals is valid: "No trades: the rule never triggered on these days", with the benchmark shown.

## 4. Metrics and comparisons

Every metric is shown for the strategy and for buy-and-hold, side by side, over the same days S to L. Computed in
Python from the integer-cent daily values; percentages are display values rounded to two decimals.

| Metric | Definition | Plain explanation (draft, for the content gate) |
|---|---|---|
| **Total return** | `(value at L − 10,000) / 10,000` | "How much the $10,000 grew or shrank over these days, after the costs chosen." |
| **Maximum drawdown** | Largest fall from a running peak of the daily closing value to a later low, as a % of that peak, with both dates | "The worst drop from a high point along the way. It shows how uncomfortable the ride was, which the final number hides." |
| **Volatility** (D8) | Sample standard deviation of the L − S daily changes in value, as a % (not annualised) | "How much the value typically moved in a day. Days spent in cash move by 0%, which lowers this number." |
| **Trades** | Number of buys and number of sells | "How often the rule acted. Each fill pays the cost setting." |
| **Days invested** (D9) | Evaluation days ending with shares held / L − S | "How much of the time the money was in the market." |
| **Costs paid** | Total slippage in dollars | "What the cost setting took from the result." |
| **Compared with buy and hold** | Difference in total return, in percentage points | "Ended N points higher / lower than buying and holding SYN-X over the same days." |

Deliberately not shown: win rate, Sharpe ratio, annualised return (CAGR), "alpha". With one synthetic year and a
handful of trades they look precise but are mostly noise, and they read like scores.

**Wording rules (tested):**

- Results describe what happened on these synthetic days, in the past tense. No "will", "expect", "predict", "best",
  "winning", "beat the market", "outperform", "guaranteed", "you should", "buy now", "sell now", "sure thing".
- A standing note on every result: "This is a hypothetical test on computer-generated prices. A rule that did well
  here can do badly on other prices. Past results, real or simulated, do not tell you what will happen next."
- Presets are never ranked or sorted by result.

## 5. Architecture

- **`services/backtest.py`** (new, pure functions, integer cents): `run(dates, bars, preset, costs)` returns the daily
  values, fills and metrics for the strategy and the benchmark, plus the two halves. It imports only
  `services.indicators` (`sma`, `rsi`) and the standard library. It **does not import or call `paper_engine`**, and
  the engine never imports it. Nothing it computes reaches the Practice Trading session, balances, orders or fills.
- **`routes/backtest.py`** (new blueprint, added to `app.py`'s registration list):
  `POST /api/backtest/run` with `{state, symbol, preset: "sma_cross"|"rsi_threshold", costs: "example"|"none"}`.
  Read-only: it never changes the session. POST only because the signed session state rides in the body (64 KB
  limit). Answers in the standard envelope with `source: null`, as `/api/analysis`.
- **Bars** come only through the public `paper_engine.market_bars(state)` (as `/api/analysis/indicators`). No other
  engine function is used.
- **Response `data`:** `symbol`, `preset`, `costs`, `window` {start_index, start_date, last_index, last_date,
  evaluation_days}, `result` (or `null` with `needed_days`, `available_days`). `result` holds `strategy` and
  `benchmark`, each {`values` [{time, value_cents}], `fills` [{index, date, side, shares, open_cents, price_cents,
  cost_cents, cash_after_cents}], `metrics`}, plus `unacted_signal`, `halves` (earlier / later, or `null`),
  `indicators` (the strategy's own series for the chart, in P4 display units), `notice`, `education`.
- **Errors:** `INVALID_STATE` (tampered or missing session), `INVALID_REQUEST` with a readable message (unknown symbol,
  preset or cost setting, extra keys, wrong types including booleans), `REQUEST_TOO_LARGE` (413), `INTERNAL_ERROR`
  logged. Documented in a new `docs/API_CONTRACT.md` section.
- **Content:** `data/strategy_guide.json`, copied word for word from an owner-approved `docs/P5_CONTENT.md` (P4 step 6
  pattern) and served by `GET /api/backtest/guide`.
- **No new dependency**, no new framework, no build step, no network, no paid or AI call; `ZERO_COST_MODE` behaviour is
  unchanged. Flask, vanilla JavaScript and the vendored Lightweight Charts 5.2.1 (line series, panes and markers are
  already used by P3/P4).

## 6. UI and UX

A **"Test a strategy"** view inside Practice Trading (D10, D12), switched with the trading workspace by a two-button
control ("Trade" / "Test a strategy", `aria-pressed`). It uses the same market, session and tickers.

- **Setup form:** ticker (the session's tickers), rule (two radio buttons with a one-line description each, and What is
  this?), costs (Example costs / No costs), Run test. The benchmark needs no choice. Nothing runs automatically.
- **Results, in order:** the Simulated label; a one-sentence outcome in plain words; the metrics table (strategy and
  buy-and-hold columns, a real `<table>` with headers); the chart; the fills list; "How this test works" (Section 3 in
  short); the earlier / later halves; the standing note.
- **Chart** (one Lightweight Charts chart, panes as in P4): price candles with **In** / **Out** markers (D11: not
  B / S, so they are not mistaken for the learner's own practice trades), the SMA 20 / 50 lines for the crossover or
  an RSI pane with 30 / 70 guides for the RSI rule, and a value pane with the strategy (solid) and buy-and-hold
  (dashed) lines. Warm-up days (before S) are marked "warm-up: indicators only". The crosshair readout gives the date,
  both values and any fill.
- **Explanations:** a card per metric and per rule, with Learn more (P4 pattern). Text goes through the content gate.
- **States:** not enough data, no trades, open position at the end, signal on the last day, too short to split,
  request error with a retry.
- **Mockup gate:** `docs/mockups/09-strategy-desktop.html` (1280), `10-strategy-phone.html` (390),
  `11-strategy-states.html`, light and dark, approved before any UI code.
- **Accessibility:** keyboard-only operation; visible focus; the canvas is `aria-hidden` with a text summary (window,
  both final values, the metrics, every fill); results announced through a polite live region; colour is never the
  only cue (solid / dashed lines, In / Out text, signed numbers with "higher" / "lower" words); WCAG AA contrast in
  both themes; 44 px targets on phones; no horizontal overflow at 390 px; focus moves to the results heading after
  Run test.

## 7. Testing

**pytest** (offline, as now):

- **Independent reference:** a separate plain implementation in the test file (loops, no shared code) of both rules,
  the fills and every metric; all 14 symbols of both scenarios at every possible L must match `services/backtest.py`
  exactly in cents and within 1e-9 for ratios (P4 `test_p4_final.py` pattern). Plus small hand-worked series with
  known crossings, RSI thresholds and drawdowns, checked against numbers written in the test.
- **Determinism:** the same request twice gives byte-identical JSON.
- **Start rules:** every preset and the benchmark hold $10,000.00 cash and no shares at the close of S; no fill before
  index 50; no crossover fill before index 51; SMA 20 already above SMA 50 on day S gives no entry until a later cross
  up; RSI below 30 on day S fills at index 50; a value of exactly 30 or 70, or exactly equal averages, behave as
  Section 3.2 says.
- **No look-ahead:** for every t, the fills and values up to t from a run with L = t equal those of the full run
  (prefix stability); changing every price after t leaves all decisions up to t unchanged; no fill is on or before
  its decision day; the endpoint never returns a date after the session's day.
- **Accounting and no borrowing:** every day `value = cash + shares × close`; cash and shares never negative after any
  fill; a buy never costs more than the cash held; final cash equals start minus buys plus sells (costs inside fill
  prices); costs paid equals the sum of `(price − open) × shares` for buys and `(open − price) × shares` for sells;
  "No costs" fills equal the open exactly.
- **Edge cases:** constant prices (RSI 50, no crossing, no trades), steadily rising and falling series, L = 68 / 69
  (69 / 70 trading days), a signal on L, a position open at the end, a price above the available cash, the
  earnings-gap day, the scripted decline, the halves at L = 128 / 129.
- **Invalid input:** each field missing, wrong type, unknown value, extra keys, booleans, tampered sessions, a body
  over 64 KB, and a seeded fuzz of 400 malformed bodies (none may give a 500).
- **Isolation:** the `paper_engine.py` hash pin still passes; `paper_market.py`, `routes/paper.py`, `indicators.py`,
  `explain.py` and `routes/analysis.py` unchanged; a test asserts `paper_engine` does not import `backtest`.
- **Wording:** guide text equals the approved document; banned phrases (Section 4) are rejected in the guide and in
  every generated sentence; the words "in-sample" and "out-of-sample" never appear in the UI text.

**Browser QA:** a new optional suite `scripts/qa/backtest.mjs` (Node built-ins, Edge, 127.0.0.1 only): both rules ×
both cost settings equal to the API, markers on the fill days, value lines equal to the API, every state, keyboard
only, phone layout, light / dark, Reset and Change market. All existing suites (343 checks) and the visual audit,
extended to the new view, must still pass. Screenshots are reviewed at each UI step and kept outside the repository
(`..\finance-app-v2-screenshots\P5\`).

## 8. Implementation roadmap

One local commit per step on `dev/v2`; no push, merge or tag without approval. pytest and `check_endpoints.py` run at
every step; browser QA from step 6 on.

| Step | Work | Gate |
|---|---|---|
| 0 | This brief | Owner decisions (done) |
| 1 | Mockups 09–11 | **Owner approval** |
| 2 | `services/backtest.py`: start rules, fills, costs, whole shares, daily values; reference, conservation and look-ahead tests | **Owner review of the maths** |
| 3 | Metrics, benchmark comparison, halves; tests | — |
| 4 | `routes/backtest.py`, `app.py` registration, API contract, validation and fuzz tests | — |
| 5 | `docs/P5_CONTENT.md`: every explanation and sentence | **Owner content review** |
| 6 | View switch, setup form, results text, metrics table, fills list, states (no chart yet) | — |
| 7 | Chart: candles with In / Out markers, strategy indicators, value pane | — |
| 8 | Explanation cards, guide endpoint, What is this? | — |
| 9 | Final QA, `scripts/qa/backtest.mjs`, docs, `P5_PROGRESS.md` | **P5 review** |

**Protected (not modified without separate approval):** `services/paper_engine.py`, `services/paper_market.py`,
`routes/paper.py`, `data/paper/scenarios/*.json`, `scripts/build_synthetic_scenario.py`,
`static/vendor/lightweight-charts/*`. P4 files `services/indicators.py`, `services/explain.py`, `routes/analysis.py`
and `data/indicator_guide.json` are imported or read only. Zero-cost mode, offline tests and the network block in
`tests/conftest.py` are unchanged.

**Expected to change:** new `services/backtest.py`, `routes/backtest.py`, `data/strategy_guide.json`,
`static/js/backtest.js` (a new file rather than growing the 2,300-line `paper.js`), tests, mockups and docs; small
edits to `app.py`, `templates/index.html`, `static/js/api.js`, `static/css/features.css`, and `paper.js` only for the
view switch.

## Owner decisions (2026-10-29)

| # | Decision |
|---|---|
| D1 | No EMA crossover in the MVP. |
| D2 | SMA rule acts on crossing events only, starting in cash (Section 3.2). |
| D3 | RSI exit at 70. |
| D4 | Cost presets "Example costs" (0.10% slippage, $0 commission, the default) and "No costs". |
| D5 | Whole shares only. |
| D6 | Current session only: bars up to the current practice day through `market_bars(state)`. |
| D7 | Common start S = index 49 (Day 50); at least 20 evaluation days (70 trading days); halves only at 40+ evaluation days each, described, not validated. |
| D8 | Volatility as daily, not annualised. |
| D9 | "Days invested" is a metric. |
| D10 | "Test a strategy" is a view inside Practice Trading, not a sixth tab. |
| D11 | Markers named In / Out. |
| D12 | Name "Test a strategy"; "Lab" is not used (taken by the AI Comparison Lab). |

## Roadmap v3 check

Roadmap v3 is not in the repository or next to it, so it cannot be checked line by line. What the repository records
of it (`docs/P2.5_PROGRESS.md`, `docs/P3_PROGRESS.md`) is consistent with this brief: synthetic scenarios with their
notice always shown, the vendored chart library, and no real data. Unresolved:

1. **Roadmap P5 wording unverified.** The owner's P5 request is the only source for P5 scope here.
2. **Portfolio-value chart.** The roadmap names a Practice Trading portfolio-value chart as a gap, deferred in P3. The
   P5 value pane charts a hypothetical test, not the learner's practice portfolio, so it does not close that gap and
   it stays deferred (not added to P5 scope).
3. **Session-bound window and synthetic-a.** With D6, synthetic-a (120 days) allows a test from Day 70 with at most 70
   evaluation days and never shows halves. If the roadmap expects a full-year backtest on every market, that would
   need a change of D6 or a new scenario, neither of which is in this scope.
