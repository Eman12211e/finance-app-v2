# P3 progress log — Practice Trading price chart

Read this first after any context reset. Roadmap v3 has no separate P3 brief; scope follows its commitments: TradingView
Lightweight Charts, vendored into `static/vendor/` with the Apache-2.0 licence and no CDN, filling the approved P2.5
chart area with candlesticks, volume, your trade markers, crosshair and zoom (plus the mockup's Daily/Weekly switch).
Base: `dev/v2` at `fed4b31` (P2.5 approved and pushed). Owner go-ahead for the dependency: 2026-10-27.

## Step 1 — Vendor the library (`3f52457`)

- `lightweight-charts@5.2.1` (published 2026-08-12) fetched with `npm pack --ignore-scripts` into an isolated folder;
  registry integrity `sha512-IVwoK1RL…a1nsQ==` verified. Copied unmodified:
  `static/vendor/lightweight-charts/lightweight-charts.standalone.production.js` (197,922 bytes, sha256 `e21cc5ca…98cf`),
  `LICENSE` (Apache-2.0) and a `NOTICE` (TradingView attribution; bundles fancy-canvas 2.1.0, MIT).
- The bundle makes no network requests (no fetch/XHR/eval); its only URL besides the licence is tradingview.com.
- `.gitattributes`: `static/vendor/** -text` keeps the bytes exact on Windows checkouts (the hash is pinned).
- `tests/test_design.py`: pinned hash, version banner, no network APIs, LICENSE and NOTICE present.
  `docs/ARCHITECTURE.md` and `README.md` record the vendored library.

## Step 2 — Price chart in Practice Trading

- `templates/index.html` loads the vendored script (deferred) before `paper.js`. If it is missing, the chart area says
  so and the rest of the tab works.
- `RENDER.chart` (replaces the placeholder): candlesticks and a volume histogram for the selected ticker from the
  `market` bars, which the server cuts at today; trade markers from the session's fills (B n below the bar for buys,
  S n above for sells; weekly view marks the week); crosshair readout line (date, open, high, low, close, volume);
  scroll/pinch zoom and drag; Daily/Weekly switch (`aria-pressed`, weekly bars built in the browser from daily ones).
  Opens on all bars up to 90, else the latest 90. Theme tokens colour the canvas, and the chart is redrawn when the
  system theme or the header toggle changes. Phones keep vertical swipes for page scrolling.
- Accessibility: the canvas is `aria-hidden`; a visible summary is its text version (period, last close, high, low,
  how many of your trades are marked, how to zoom).
- Licence credit: the in-chart TradingView logo is off; a visible line under the chart, "Chart by TradingView
  Lightweight Charts™, © 2026 TradingView, Inc.", links to tradingview.com (`noopener noreferrer`), as the licence asks
  (NOTICE updated).

**Checks:** pytest 361 passed (+1 vendor test, +3 chart tests; the placeholder assertion now checks the chart).
`check_endpoints.py`: 9 SKIP, exit 0, data file restored. Headless Edge over the DevTools protocol, server on 5055 in
zero-cost demo mode: workflows 198/198 (both markets, 1280 and 390: canvas renders at 16:9 / 4:3, summary and legend,
credit link, chart ends on today and marks the fill, Weekly switch keeps focus, crosshair readout follows the mouse,
plus every P2.5 workflow); visual audit clean on all 20 tab/width/theme screens; header theme toggle repaints the
canvas (white → #172024); only the local server contacted; no console errors. Chart screenshots reviewed at day 3 and
day 161, daily and weekly, 1280 light and 390 dark.

**For owner review:** zoom resets when the ticker, day or timeframe changes (the chart is rebuilt with its region);
with a few days of data the bars sit at the left and the chart fills rightward as days pass; no portfolio-value chart
(the roadmap names it as a gap but not as P3 scope).
