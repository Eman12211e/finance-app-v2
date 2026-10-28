# Optional browser QA (`scripts/qa/`)

Repeatable headless-browser checks for the Practice Trading tab and a visual audit of the whole app. They are
**optional**: the app and `pytest` never need them, they add no runtime dependency and no npm package, and they contact
nothing but `127.0.0.1`. They drive Edge or Chrome over the DevTools protocol with Node's built-in `WebSocket` and
`fetch` (Node 22 or later).

## Run

```
node scripts/qa/run.mjs [output-dir] [suite ...]
```

`run.mjs` refuses to start if something already answers on its port, starts the app with `ZERO_COST_MODE=1`,
`DATA_MODE=demo` and `WARM_CACHE=0` (and checks `/api/health` says so), starts a headless browser with a throwaway
profile, runs the suites, writes `report.txt` plus each suite's `results.txt` and screenshots, and stops only the
processes it started. Default output: `../finance-app-v2-screenshots/qa-run/` next to the repository.

Environment: `PYTHON` (a Python with the app's requirements; default `python`), `BROWSER` (path to `msedge` or
`chrome`; common install paths are tried), `QA_PORT` (default 5055; the browser's debugging port is `QA_PORT + 4000`).
The exit code is 0 only when every chosen suite passes.

## Suites

| Suite | Checks |
|---|---|
| `workflows` | P2.5/P3: both markets at 1280 and 390 px; start screen, keyboard ticker search, Max, preview / Back / confirm, fills and toasts, Next 5 days, sell and realized P/L, chart (16:9, readout, crosshair, Daily/Weekly, today's last bar, trade markers, credit link), phone trade sheet (dialog, Tab trap, Escape), history filter, More menu, Change market, reload, journal never sent, Tab order |
| `overlays` | P4 step 4: SMA 20/50 and EMA 12/26 equal to the API, two-line limit, solid/dashed, Not enough data, readout, ticker / day / theme redraws, saved choice, Reset, phone sheet |
| `panes` | P4 step 5: RSI 14 and MACD 12-26-9 equal to the API, chart height per pane, shared crosshair, Not enough data, weekly completed weeks and Partial Week, phone |
| `explanations` | P4 step 6: one card per indicator, headings, readings equal to the API, Learn more (keyboard, kept open), What is this? without switching on, Not enough data, Partial Week, Final Short Week, phone |
| `drawings` | P4 step 7: horizontal and trend lines by mouse, touch and keyboard, typed-price validation, storage as dates and prices, weekly mapping and label room, per ticker, Remove, Clear with confirmation, Reset and Change market, nothing sent |
| `visual_audit` | All five tabs × 1280 / 390 px × light / dark: screenshots plus overflow, clipped text, WCAG text contrast, unnamed controls, broken ARIA references, duplicate ids, small targets, console errors, hosts contacted; the header theme toggle repaints the chart |

A single suite can also be run against an app and browser you started yourself:
`node scripts/qa/<suite>.mjs <devtools-websocket-url> <output-dir> <app-base-url>`.
