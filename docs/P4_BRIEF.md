# P4 — Analysis Toolbox: approved brief

Owner approval: 2026-10-27, all six decisions below. Base: `dev/v2` at `3086342` (P3, pushed).
Progress and checks are logged in `docs/P4_PROGRESS.md` once implementation starts.

## Scope

SMA, EMA, RSI and MACD on the Practice Trading price chart; horizontal-line and trend-line drawing tools; a plain
explanation per indicator of what it shows and what its current reading means, worded as education, never as a
signal. Synthetic data, zero-cost mode, offline tests, vanilla JavaScript, no build step.

## Approved decisions

1. Indicator maths in Python (`services/indicators.py`), served by a new signed-session endpoint
   (`routes/analysis.py`, `POST /api/analysis/indicators`).
2. Preset periods only: SMA 20 / 50, EMA 12 / 26, RSI 14, MACD 12-26-9. No free-entry periods.
3. Drawings live only in the browser (localStorage, per session and ticker), are never sent to the server, and are
   cleared by Reset and Change market.
4. A mockup gate (Step 1) before any UI code.
5. At most two overlays on the price pane and two lower indicator panes.
6. The headless-browser QA script is committed as an optional tool under `scripts/qa/` (Node and Edge; outside pytest).

## Requirements added by the owner

- Indicator calculations never see simulated future prices.
- Weekly indicators use completed weeks only; the unfinished week is shown on the price chart as a Partial Week;
  too little history shows "Not enough data" (rules below, documented and tested for SMA, EMA, RSI and MACD).
- RSI and MACD edge cases are tested, including constant prices and insufficient history.
- Indicator values are educational only and never feed trading-engine calculations.
- No additional runtime dependency and no external market-data request.
- `services/paper_engine.py`, `services/paper_market.py` and `routes/paper.py` are not modified.
- The TradingView attribution line and all P3 behaviour stay.

## Architecture

- **`services/indicators.py`** (new): pure functions over integer-cent bars.
  - SMA(n): mean of the last n closes.
  - EMA(n): seeded with the SMA of the first n closes, then `k = 2 / (n + 1)`.
  - RSI(14): Wilder's smoothing of average gain and loss. Constant prices (no gains and no losses) give 50; only gains
    give 100; only losses give 0.
  - MACD(12, 26, 9): EMA12 − EMA26, signal = EMA9 of MACD, histogram = MACD − signal.
  - Too little history gives `null`, shown as "Not enough data" (no value is invented): SMA and EMA need n closes,
    RSI 15, MACD 26 and its signal 34 (daily closes, or completed weeks on the weekly view).
  - Values are display-only floats in dollars, rounded to 4 decimals. They never reach `paper_engine` or balances.
- **No look-ahead.** The endpoint reads bars only through `paper_engine.market_bars(state)`, which verifies the
  signed session and stops at the current simulated day. A test checks that every value computed on day *t* equals
  the same value computed with the whole history up to the scenario's end, cut at *t* (prefix stability).
- **Weekly data rules (owner-approved 2026-10-27).**
  1. A weekly bar holds the trading days of one Monday-to-Friday calendar week and is dated by its first trading day
     (the P3 chart already does this; the server becomes the only implementation and the JavaScript copy is removed).
  2. A week is **completed** once its last trading day has closed: its Friday is on or before today. The scenario's
     short first week (Thu 2 and Fri 3 Jan 2025) is completed: those are all of its trading days. The scenario's
     final week is shorter (synthetic-b ends on Wed 17 Dec 2025). It stays a Partial Week until the final simulated
     day is reached; on that day it becomes completed, is included in the weekly calculations and is labelled
     **Final Short Week** (it has fewer trading days than a full week). API status per weekly bar: `"complete"`,
     `"partial"` or `"final_short"`.
  3. Weekly SMA, EMA, RSI and MACD are calculated from **completed weeks only**. The unfinished week never enters a
     weekly indicator, so weekly indicator values change only when a week completes.
  4. The unfinished week may appear on the price chart as a candle built from its days up to today, labelled
     **Partial Week** (in the chart, the readout and the summary) and flagged `"partial": true` in the API.
  5. No calculation, daily or weekly, uses a price after the current session day.
  6. When completed history is too short, the indicator shows **"Not enough data"** and draws nothing; no value is
     estimated. Example: on day 161 (Thu 14 Aug 2025) there are 32 completed weeks, so weekly SMA 20, EMA 12, RSI 14
     and the MACD line have values, but the MACD signal line (needs 9 MACD values, 34 weeks) is "Not enough data".
  - Tests, for each of SMA, EMA, RSI and MACD: weekly values use completed weeks only and are unchanged by the
    partial week's days; weekly values change only on the day a week completes; "Not enough data" (null) below the
    required number of completed weeks; weekly bars equal aggregates of the daily bars up to today; the partial flag
    is set exactly when the last week is unfinished; the scenario's first and last weeks follow rule 2; the final
    week changes from Partial Week (the day before the last day) to Final Short Week (the last day), and only then
    enters the weekly indicators.
- **`routes/analysis.py`** (new blueprint, registered in `app.py`). Body:
  `{state, symbol, timeframe: "daily"|"weekly", indicators: [{type, period}]}`. Validates the indicator types and preset
  periods, the symbol and the limits (two overlays, two panes), and answers in the usual envelope. Invalid sessions
  return `INVALID_STATE`, as in `/api/paper`. Documented in `docs/API_CONTRACT.md`.
- **Drawings** in localStorage (`paper-drawings-v1`), anchored by date and price so they show on Daily and Weekly.
- **Explanations** in `data/indicator_guide.json`, written now for owner review, labelled "Our plain summary". A test
  rejects advice wording ("you should", "buy now", "sell now", "guaranteed", "sure thing").

## Mockup-gate decisions (owner-approved 2026-10-27)

1. Indicator colours stay as mocked (indigo solid, magenta dashed), with line styles and on-chart names so colour is
   never the only cue.
2. Each explanation card shows the short current reading by default; a Learn more control reveals what it shows, how
   people read it and what to watch out for.
3. All indicators start switched off.
4. Drawing as mocked: by mouse or touch a trend line snaps to the nearest bar's date with the price following the
   pointer; by keyboard a trend line joins two chosen days' closes and a horizontal line uses a typed price.
5. "What is this?" opens an indicator's explanation without switching the indicator on.
6. The scenario's final short week becomes completed only on the final simulated day and is labelled Final Short
   Week (weekly rule 2).

## UI (Practice Trading chart area only)

Toolbar under the chart heading: Indicators (checkboxes with preset periods), Draw (Horizontal line, Trend line),
Clear drawings. SMA and EMA as overlays; RSI pane with 30 / 70 guides; MACD pane with MACD, signal and histogram. The
crosshair readout gains indicator values. An explanation card per active indicator below the chart (current
reading, then Learn more). Keyboard
alternatives for drawing (a horizontal line at a typed price; a trend line between two chosen dates' closes) and a
"Your drawings" list with remove buttons. The text summary names the active indicators. Phones: the same controls,
wrapped. Mockups: `docs/mockups/06`–`08`.

## Dependencies

None new. Lightweight Charts 5.2.1 (vendored in P3) provides line and histogram series, panes, price lines and series
primitives for trend lines.

## Testing

pytest: maths (worked examples, constant / rising / falling series, insufficient history, prefix stability, weekly
aggregation and partial weeks), endpoint (validation, limits, tampered session, nothing past today, no network),
static page checks (wiring, accessibility attributes, drawings never in a request body, no advice wording). Headless
Edge via `scripts/qa/`: toggle each indicator and compare readouts with the endpoint, draw and remove by mouse and
keyboard, drawings survive reload and Reset clears them, all tabs × 1280 / 390 × light / dark, every P2.5 and P3 flow.

## Sequence (one local commit per step; no push without approval)

0. This brief; P3 decisions recorded (`ea5406b`; weekly rules amended in a follow-up commit).
1. Mockups (desktop, phone, panes, drawing, explanation cards) (`bb2a53c`, updated for the weekly rules).
   **Gate: owner approval.**
2. `services/indicators.py` and tests.
3. `routes/analysis.py`, tests, API contract; the chart uses the server's weekly bars.
4. Toolbar, SMA / EMA overlays, readout values.
5. RSI and MACD panes.
6. Explanation cards and guide content. **Gate: owner content review.**
7. Drawing tools, keyboard alternatives, drawings list, browser storage.
8. Full QA, `scripts/qa/`, docs. **Gate: P4 review.**
