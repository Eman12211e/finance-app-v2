# P4 progress log — Analysis Toolbox

Read this first after any context reset. Brief and decisions: `docs/P4_BRIEF.md`. Base: `dev/v2` at `3086342` (P3).

| Commit | Step |
|---|---|
| `ea5406b`, `02a0b55`, `71a2ba2` | 0: brief, P3 decisions, weekly rules, mockup-gate decisions |
| `bb2a53c`, `33b5975` | 1: mockups 06–08 (approved) |
| `bbc7fb2` | 2: `services/indicators.py` + 39 tests (approved) |
| `67a3bca` | 3: analysis endpoint (approved) |
| `03b553d` | 4: SMA and EMA overlays (approved) |
| `c15c93a` | 5: RSI and MACD panes (approved) |
| `d8b90d7` | 6 content: final explanation text (approved) |
| `287a3c8` | 6: explanation cards (approved) |
| `8607d0a` | 7: drawing tools (approved) |
| `dc1fabb` | 7b: weekly label room; Clear drawings confirmation |
| this commit | 8: final QA, `scripts/qa/`, independent maths check |

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

## Step 6 — Educational explanations

- **Text:** `data/indicator_guide.json`, copied word for word from the approved `docs/P4_STEP6_CONTENT.md` (a test
  keeps them identical). Static: no AI, no network. `GET /api/analysis/guide` serves it.
- **Readings** are chosen on the server (`services/explain.py`, called by `/api/analysis/indicators` for each
  indicator) from the unrounded values of `indicators.raw()` (owner refinement): RSI zones at 30 / 50 / 70, the close
  against SMA/EMA, MACD's side of zero, its signal line and the histogram's change (widened, narrowed, crossed,
  unchanged; a zero gap gets no change sentence). Numbers are rounded only for display, and get extra decimals when
  the usual rounding would contradict the chosen sentence (RSI 69.996 shows as "69.996", an average 0.2 cents under
  the close as "$199.958"). Not enough data names what is needed and what exists; the weekly prefix, Partial Week and
  Final Short Week sentences follow the approved text. `indicators.compute()` is now `rounded(raw())`, so chart values
  are unchanged.
- **Cards** (`paper.js`, `features.css`): one per active indicator under the chart, heading with name, period and line
  style plus the Simulated mark, the API's reading, a closed **Learn more** disclosure (Our plain summary, What it
  shows, How people read it, Watch out; open state kept across redraws) and the footer. The browser shows strings
  only; it calculates nothing.
- **What is this?** beside every preset in the Indicators menu (outside the checkbox's label): opens the full
  explanation inside the popover or phone sheet without switching the indicator on; one open at a time
  (`aria-expanded`, `aria-controls`, a specific name such as "What is SMA 50?").

**Found and fixed while testing:** in the two-column card grid an opened Learn more stretched the neighbouring card to
the same height; cards now align to the top.

**Checks:** pytest 535 passed (+43 `tests/test_explain.py`: every reading branch, RSI at and around 30 / 50 / 70,
display rounding that never contradicts the sentence, SMA/EMA and MACD from unrounded values, Not enough data for
every preset, weekly prefix / Partial Week / Final Short Week, the guide equal to the approved document, banned
phrases, the API's readings and the guide route; +4 static front-end checks). Mutation checks: choosing the RSI zone
from the rounded value, dropping the extra display decimals, and comparing a zero MACD gap each fail the tests.
`check_endpoints.py`: 9 SKIP, exit 0, data file restored. Headless Edge (zero-cost demo server): explanation checks
22/22 (cards and headings for all four presets, readings equal to the API daily and weekly, footer and labelled
regions, Learn more closed by default and opened by keyboard, kept open across a theme redraw, What is this? for an
indicator that is off without switching it on or sending a request, one explanation at a time, Not enough data on day
11, Final Short Week on day 250, phone: one column, no overflow, What is this? inside the sheet; only local requests;
no console errors); panes 26/26; overlays 36/36; P2.5/P3 workflows 198/198; visual audit clean on all 20 tab/width/
theme screens. Screenshots (not committed): `C:\Users\emanl\finance-app-v2-screenshots\P4\step-6\`.

## Step 7 — Drawing tools

- **Storage:** `paper-drawings-v1` in localStorage, keyed by market and ticker; each drawing is
  `{id, kind: "h", price}` or `{id, kind: "t", a: {date, price}, b: {date, price}}` (ISO dates, dollar prices to the
  cent; never pixels). Re-checked when read (shape, dates in order, finite positive prices), at most 20 per ticker,
  cleared with the session by Reset and Change market. Never sent to the server and never part of prices, orders,
  fills or the portfolio.
- **Chart:** horizontal lines are the candle series' price lines (dashed, in the text colour, titled "Your line" with
  an axis label); trend lines are a series primitive that turns dates and prices into pixels only while drawing, so
  zoom and scroll follow. On the weekly view a date maps to the week it falls in (the same rule as trade markers).
  Adding or removing a drawing updates the live chart in place; nothing is rebuilt, so the zoom stays.
- **Mouse and touch:** Horizontal line / Trend line toolbar buttons (`aria-pressed`) start a mode with a status banner
  ("click or tap the chart…", "…the second point…", Esc or Cancel ends it). A press that does not move counts; a drag
  still pans. Points snap to the nearest bar's date; the price follows the pointer, rounded to the cent. Price pane
  only. A second point on the same date is refused with a reason.
- **Keyboard:** a typed horizontal-line price (validated: 0.01 to 100,000, up to two decimals, "$" and "," allowed;
  Enter adds) and a trend line between two chosen days' closing prices (daily closes up to today from the watchlist's
  bars; the end must be after the start). Errors set `aria-invalid` and are announced.
- **Your drawings** panel under the chart: each drawing with a Remove button named after it, Clear drawings (also in
  the toolbar), a polite status line ("Added: …", "Removed: …"). The chart's text summary lists every drawing; on the
  weekly view it names the week each end falls in.

**Found and fixed while testing:** the chart library treats a quick second click or tap (under about half a second)
as a double-click and drops it, so a trend line's second point could be lost. Drawing now uses the browser's pointer
events on the chart (a press that does not move), which report every click and tap.

**Checks:** pytest 539 passed (+4 static Step 7 checks). `check_endpoints.py`: 9 SKIP, exit 0, data file restored.
Headless Edge (zero-cost demo server): drawing checks 36/36 (mouse horizontal and trend lines, same-date refusal, Esc
and Cancel, no drawing without a mode, typed prices refused and accepted, keyboard trend lines on the days' closes,
summary, portfolio unchanged, reload, weekly mapping of a Wednesday to its week, theme change, per-ticker lists,
Remove with focus kept in the panel, Clear, Reset and Change market clearing, touch taps for both kinds, phone
without overflow, no drawing data in any request, only local requests, no console errors); explanations 22/22; panes
26/26; overlays 36/36; P2.5/P3 workflows 198/198; visual audit clean on all 20 tab/width/theme screens.
Screenshots (not committed): `C:\Users\emanl\finance-app-v2-screenshots\P4\step-7\`.

**Open:** on the weekly view the "Your line" labels at the right edge can overlap the Partial Week marker's text.

## Step 7 adjustments (`dc1fabb`)

- **Label overlap:** on weekly charts whose last bar carries the Partial Week or Final Short Week label, the view
  leaves about 120 px after the last bar, so the label never meets the "Your line" labels at the right edge. Empty
  slots also narrow the bars, so the number of slots is solved for (`k = 120·n / (W − 120)`, or 120 / 28 when bars are
  at their widest). The measured gap is recorded on the chart container (`data-week-label-room`) for the regression
  check: 131 px at 1280, 122 px at 390. Daily charts and weeks without the label keep their framing.
- **Clear drawings asks first** (toolbar and panel): "Clear all N drawings on SYN-TEC1? This cannot be undone." with
  "Yes, clear drawings" and "Keep drawings" (focused; Esc keeps). Individual Remove stays immediate.

## Step 8 — Final P4 QA

### Review against `docs/P4_BRIEF.md`

| Brief item | Status |
|---|---|
| Decision 1: maths in Python behind a signed-session endpoint | `services/indicators.py`, `routes/analysis.py` (`POST /api/analysis/indicators`) |
| Decision 2: preset periods only | SMA 20/50, EMA 12/26, RSI 14, MACD 12-26-9; anything else is `INVALID_REQUEST` |
| Decision 3: drawings browser-local, cleared by Reset / Change market | `paper-drawings-v1`; never sent; cleared with the session |
| Decision 4: mockup gate | Mockups 06–08 approved before UI code |
| Decision 5: two overlays, two panes | Enforced in the menu and by the API |
| Decision 6: optional QA scripts | `scripts/qa/` (this step) |
| No future prices | Bars only through `market_bars(state)`; prefix-stability tests for every preset, day and the API |
| Weekly rules, Partial Week, Final Short Week | Completed weeks only; Partial Week shown and never calculated; Final Short Week on the final day; tested in maths, API, readings and browser |
| RSI / MACD edge cases | Constant, rising, falling, insufficient history, zero gap, crossings |
| Educational only | Readings and guide text reviewed and tested for banned wording; the engine never imports or receives indicator or drawing data |
| No new runtime dependency; no external data | `requirements*.txt` unchanged; Lightweight Charts vendored in P3; only `127.0.0.1` contacted in every browser run |
| Protected files untouched; TradingView credit kept | `paper_engine.py`, `paper_market.py`, `routes/paper.py` unchanged since P2 (`8c94e46`); credit line on every chart |

Beyond the brief (documented in the steps above): `GET /api/analysis/guide` (What is this? for indicators that are
off), readings chosen on the server from unrounded values (owner refinement), the Indicators menu as checkboxes
(owner-approved in step 4), and drawing through pointer events (the chart drops quick second clicks).

### Results

- **pytest:** 560 passed, 0 failed (P3 ended at 361; P4 added 199). New in this step: `tests/test_p4_final.py` (19):
  every SMA, EMA, RSI and MACD series for all 14 symbols of both markets equal to a separate, plain reference
  implementation within 1e-9, and the API's daily and weekly values for all 12 synthetic-b symbols equal to that
  reference; the QA scripts use Node built-ins only, contact only 127.0.0.1, need no `package.json`, and the runner
  refuses to run unless `/api/health` reports zero-cost demo mode.
- **`check_endpoints.py`:** 9 SKIP (zero-cost mode), exit 0, `data/endpoint_check.json` restored.
- **Browser QA** (`node scripts/qa/run.mjs`, headless Edge, app on 127.0.0.1:5055 in zero-cost demo mode):
  workflows 198/198, overlays 36/36, panes 26/26, explanations 22/22, drawings 41/41, visual audit 20/20 — 343 checks,
  0 failed. The visual audit now skips visually hidden text (the phone tab names), so a clean run needs no caveat.
- **Screenshots:** `C:\Users\emanl\finance-app-v2-screenshots\P4\final\` (one folder per suite, `report.txt`,
  `results.txt` per suite). Earlier steps: `...\P4\step-5\`, `...\step-6\`, `...\step-7\`. Not committed.

### Accessibility and responsiveness

Covered by the suites: keyboard-only ticker search and ordering, tab bar arrows / Home / End and hash routing, Tab
reaches every ticket control, the Indicators menu and phone sheets (dialog, Tab kept inside, Escape and Done return
focus), Learn more and What is this? by keyboard with specific accessible names, drawing modes ended by Esc, the
keyboard drawing forms (`aria-invalid`, announced status), Remove keeping focus in the panel, the Clear confirmation
focusing "Keep drawings", focus kept on Next day and the timeframe buttons through redraws; every chart has a text
summary (prices, trades, lines, panes, Partial / Final Short Week, drawings); gains and losses never rely on colour
alone; no horizontal overflow at 390 or 1280 px on any tab; text contrast passes WCAG AA in both themes; no console
errors or warnings.

### Remaining limitations

- Not tested with a real screen reader or on real phones; touch was emulated.
- The QA scripts need Node 22+, Edge or Chrome, and `PYTHON` pointing at a Python with the app's requirements (this
  machine uses the V1 virtual environment). They are not run by pytest or CI, and their expectations use synthetic-b's
  dates and prices, so a regenerated market would need script updates.
- On phones the weekly chart's bars are narrow (about 4.5 px) when the label room is applied.
- Drawings are on the price pane only; there is no undo after Clear (it asks first); at most 20 per ticker.
- Weekly MACD's signal line shows "Not enough data" until week 34 of the scenario (by design: completed weeks only).
- The chart's zoom resets on a new ticker, day or timeframe (owner-approved in P3); adding or removing a drawing keeps it.
