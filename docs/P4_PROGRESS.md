# P4 progress log — Analysis Toolbox

Read this first after any context reset. Brief and decisions: `docs/P4_BRIEF.md`. Base: `dev/v2` at `3086342` (P3).

| Commit | Step |
|---|---|
| `ea5406b`, `02a0b55`, `71a2ba2` | 0: brief, P3 decisions, weekly rules, mockup-gate decisions |
| `bb2a53c`, `33b5975` | 1: mockups 06–08 (approved) |
| `bbc7fb2` | 2: `services/indicators.py` + 39 tests (approved) |
| `67a3bca` | 3: analysis endpoint (approved) |
| `03b553d` | 4: SMA and EMA overlays (approved) |
| this commit | 5: RSI and MACD panes |

## Step 3 — Analysis endpoint

- `routes/analysis.py` (new blueprint, registered in `app.py`): `POST /api/analysis/indicators`. Validates the body
  (object), timeframe, indicators (presets only, each once, at most two overlays and two panes) and symbol; the
  session goes through the engine's public `market_bars(state)`, which verifies the signature and stops at today. Only
  the verified scenario's length is read besides that, to know whether today is the final day (Final Short Week).
  Daily bars and series up to today; weekly bars from `indicators.weekly`, weekly series from completed weeks only,
  padded with `null` for the Partial Week so they line up with the bars. Own request helpers, so `routes/paper.py` is
  untouched. Any unexpected error is logged and returned as the standard `INTERNAL_ERROR` envelope.
- Front end: the P3 JavaScript weekly aggregation is removed. The Weekly view asks the endpoint (bars only, no
  indicators yet), caches the reply per market, ticker and day, and ignores replies for an earlier ticker or day. The
  last weekly bar is drawn hollow and labelled "Partial Week", or labelled "Final Short Week", in the chart marker,
  the readout and the summary. New `Api.postAnalysis` in `api.js`.
- `docs/API_CONTRACT.md`: new "Analysis Toolbox" section.

**Found and fixed while testing:** an indicator `type` sent as a JSON object raised `TypeError: unhashable type` (a
500). The type is now checked to be a string first; a seeded fuzz test of 400 malformed bodies guards the class.

**Checks:** pytest 479 passed (400 before; +78 `tests/test_analysis.py`, +1 static check; one P3 assertion updated for
the rewritten daily-bars line). `check_endpoints.py`: 9 SKIP, exit 0, data file restored. Engine,
`paper_market.py` and `routes/paper.py` unchanged since P3. Headless Edge (server on 5055, zero-cost demo mode): P2.5/P3
workflows 198/198 (including Daily/Weekly); weekly labels on day 161 (Thursday: "Partial Week of Aug 11, 2025"), day
162 (Friday: plain "Week of Aug 11, 2025") and day 250 ("Final Short Week of Dec 15, 2025", "final 3 trading days");
no console errors.

## Step 4 — SMA and EMA overlays

- **Toolbar and menu** (`static/js/paper.js`, `features.css`): an Indicators button (`aria-expanded`, `aria-controls`)
  under the chart heading opens a popover on desktop and a bottom sheet on phones (`role="dialog"`, `aria-modal`,
  Tab kept inside, scrim). "On the price (2 at most)": SMA 20, SMA 50, EMA 12, EMA 26 as checkboxes; with two on,
  the others are disabled and a note says why. Escape, Done or a click elsewhere closes it and returns focus. All off
  by default.
- **Data:** one `/api/analysis/indicators` request per market, ticker, day, timeframe and overlay set, for Daily and
  Weekly alike (bars and series together; the daily chart no longer reads `/api/paper/market`). Replies are cached for
  theme redraws and ignored if anything changed meanwhile. No indicator maths in JavaScript.
- **Lines:** the first active overlay is a solid `--ind-a` line, the second a dashed `--ind-b` line; each is named on
  the price scale. New tokens in `style.css` (light and both dark blocks). Readout: each line's value at the
  crosshair, "Not enough data", or "not calculated for a Partial Week". A legend under the chart gives each line's
  latest settled value; the text summary lists the lines with their style and value, and says weekly lines use
  completed weeks only.
- **Preferences** in localStorage (`paper-indicators-v1`), re-validated on load (presets only, two at most), cleared by
  Reset and Change market. Sent only inside chart requests; the trading engine never sees them.

**Found and fixed while testing:** after Step 4 stopped redrawing the chart when the watchlist reloads (to avoid a
double draw), advancing a day left the chart on the previous day's values. The chart now redraws when a day passes.

**Checks:** pytest 483 passed (+4 static Step 4 checks; two Step 3 assertions updated for the generalised chart
request). `check_endpoints.py`: 9 SKIP, exit 0, data file restored. Headless Edge (zero-cost demo server): overlay
checks 36/36 — default off, keyboard menu, the four presets each equal to the API, two-line limit, solid/dashed,
"Not enough data" (SMA 50 on day 41, weekly SMA 50 on day 161), readout and crosshair values, no bar after today,
redraw on ticker change, next day and theme toggle, reload keeps and Reset clears the choice, weekly values from
completed weeks with the Partial Week uncalculated, phone sheet (dialog, Tab trap, Done), no overflow, only local
requests, no console errors; P2.5/P3 workflows 198/198; visual audit clean on all 20 tab/width/theme screens with two
overlays on.

## Step 5 — RSI and MACD panes

- **Menu:** a second group, "Below the chart (2 at most)": RSI 14 and MACD 12-26-9. Both panes can be on with two
  price lines (four indicators, the API's maximum). Saved choices hold lines and panes together and are re-checked
  on load (approved presets, each once, within each limit); MACD's period is a list, so presets are compared by value.
- **Panes** are panes of the same Lightweight Charts chart, so the time axis, zoom, scrolling and crosshair are shared.
  RSI: fixed 0-100 scale, dashed guides at 30 and 70 with axis labels, one decimal. MACD: histogram (green above zero,
  red below), solid MACD line, dashed Signal line, dotted zero line; the scale always includes zero (weekly MACD can
  sit far above it). The chart grows taller per pane (desktop 16:9, 16:12, 16:14.5; phone 4:3, 4:4.3, 4:5.4) and the
  price pane keeps the largest share.
- **Number formats** are per series now (the chart-wide "$" formatter is gone): dollars on the price, candles and
  lines; RSI 0-100 with one decimal; MACD plain with two decimals.
- **Readout, legend and summary** carry the pane values: "RSI 14 69.1", "MACD 12-26-9 MACD 5.51, signal 4.76,
  histogram 0.75", "Not enough data" per value, and "not calculated for a Partial Week". The summary describes RSI as
  0 to 100 with guides at 30 and 70.

**Found and fixed while testing:** on the weekly chart the MACD values were all above zero, so the auto-fitted scale
hid the zero line. The MACD scale now always includes zero.

**Checks:** pytest 488 passed (+5 static Step 5 checks; the zero-line check is part of one of them; three Step 3/4
assertions updated for the shared line-and-pane code). `check_endpoints.py`: 9 SKIP, exit 0, data file restored.
Headless Edge (zero-cost demo server): pane checks 26/26 (menu groups, chart height per pane, RSI and MACD values equal
to the API daily and weekly, four indicators at once, line limit kept, readout and summary, crosshair in the MACD pane
drives the readout, Not enough data on day 11 for both and day 21 for MACD, weekly MACD signal Not enough data with 7
of 9 values, Partial Week not calculated, Daily/Weekly switching, theme repaint, reload, Reset, phone sheet with six
presets, no overflow, only local requests, no console errors); overlay checks 36/36; P2.5/P3 workflows 198/198;
visual audit clean on all 20 tab/width/theme screens with all four indicators on. Screenshots (not committed):
`C:\Users\emanl\finance-app-v2-screenshots\P4\step-5\`.
