# P4 progress log — Analysis Toolbox

Read this first after any context reset. Brief and decisions: `docs/P4_BRIEF.md`. Base: `dev/v2` at `3086342` (P3).

| Commit | Step |
|---|---|
| `ea5406b`, `02a0b55`, `71a2ba2` | 0: brief, P3 decisions, weekly rules, mockup-gate decisions |
| `bb2a53c`, `33b5975` | 1: mockups 06–08 (approved) |
| `bbc7fb2` | 2: `services/indicators.py` + 39 tests (approved) |
| `67a3bca` | 3: analysis endpoint (approved) |
| this commit | 4: SMA and EMA overlays |

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
