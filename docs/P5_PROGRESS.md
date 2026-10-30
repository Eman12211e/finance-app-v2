# P5 progress log — Test a strategy

Read this first after any context reset. Brief and decisions: `docs/P5_BRIEF.md`. Base: `dev/v2` at `e929096` (P4).

| Commit | Step |
|---|---|
| `2e5d909` | 0: brief, owner decisions D1–D12, day numbering, start and entry rules |
| `f3e2c3c` | 1: mockups 09–11 (approved); warm-up Days 1–50 kept apart from evaluation |
| this commit | 2: `services/backtest.py` + tests (for mathematical review) |

## Step 2 — Backtesting engine

- **`services/backtest.py`** (new, pure functions, integer cents, no state): `fill_price`, `decide`, `simulate`, `run`.
  Imports only `services.indicators` (`sma`, `rsi`, unrounded floats); never imports or calls the Practice Trading
  engine or market module. Callers pass bars up to the last day they may see; indicators are computed from those bars
  alone.
- **`simulate(dates, bars, rule, costs, start=49)`**: cash $10,000.00 and no shares at the close of `start`; each day
  t from `start` to the last bar: fill yesterday's decision at today's open, record cash, shares, close and value at
  today's close, then decide from data up to today. Returns daily `values`, `fills` (signal day, fill day, side,
  shares, open, fill price, amount, cost, cash after), `skipped` entries (cash below one share's price),
  `unacted_signal` (a decision on the last day) and `costs_paid_cents`. `start` is a parameter so step 3's halves can
  reuse it; `run()` always uses 49.
- **`run(dates, bars, rule, costs)`**: the rule (`sma_cross` or `rsi_threshold`) and `buy_hold` on the same bars from
  the same start; under 70 bars it returns `result: None` with `needed_days: 70` and `available_days`.
- **Rules as in brief section 3.2:** crossings need both averages on both days, equal counts as not above; RSI
  thresholds are strict (exactly 30 or 70 does nothing); buy and hold decides once, at the close of its start day.
  Slippage: buy `ceil(open × 10010 / 10000)`, sell `floor(open × 9990 / 10000)`; "none" fills at the open.
- **No borrowing:** a buy spends `floor(cash / price) × price ≤ cash`; a sell sells exactly the shares held; the
  engine raises if cash or shares ever go negative (unreachable, and tested).
- Not in this step: metrics, halves, API, UI (steps 3, 4, 6–8).

**For the mathematical review:**

1. Buy and hold that cannot afford one share is skipped and never retries (only reachable with test data: the
   dearest synthetic share is about $165).
2. A crossing on a run's start day itself is acted on when the averages exist on the day before. For the main window
   this cannot happen (SMA 50 first exists on Day 50, so the first visible cross is on Day 51); it matters only for the
   later half in step 3, whose start day has full history.
3. Decisions compare the shared indicators' floats. The reference compares exact integers (SMA) and exact fractions
   (RSI); they agree on every symbol, rule, cost setting and tested window.
4. A sell fill price for a 1-cent open under example costs would round down to 0; synthetic prices never come close.

**Checks:** pytest 679 passed (560 before; +119 `tests/test_backtest.py`):

- a separate reference (exact arithmetic, whole shares counted one at a time) equal to the engine's complete output
  for every symbol of both markets, all three rules and both cost settings, at four window ends each;
- accounting replayed every 7th window end for every symbol, rule and cost setting: value = cash + shares × close
  every day, cash and shares never negative, a buy never above the cash and all in, sells exactly the shares held,
  costs inside the fill prices, final cash = start − buys + sells, costs paid = the sum of fill costs;
- the same start for both sides on the same dates (Day 50 close, $10,000.00, no shares), no fill before Day 51, no
  crossover fill before Day 52, buy and hold filled once at the Day 51 open; no presumed entry when SMA 20 is already
  above SMA 50 on Day 50 (real symbols); RSI below 30 on Day 50 fills at the Day 51 open;
- boundaries: equal averages, equal-then-above, above-then-equal, missing averages, RSI at, just below and just above
  30 and 70, holding and not holding; constant prices and a steady rise give no trades;
- fills: the next open across a 20% gap and on the scenario's scripted earnings gap, whole-share remainder kept as
  cash, a price above the cash skipped, cash exactly spent to zero;
- 69 bars give no result and 70 give 20 daily changes; a signal on the last day reported and filled by the longer run;
- prefix stability at every window end for every symbol and rule; changing every later price changes no earlier value
  or decision; repeat runs byte-identical and inputs untouched; unknown rules, cost settings and impossible windows
  refused; the engine does not reference the Practice Trading modules and they do not reference it.

Mutation checks (each made one at a time, then the file restored byte for byte): filling at the previous close,
treating equal averages as above, a non-strict RSI threshold, rounding a buy price down, reading tomorrow's RSI, and
starting a day early each fail the tests. `check_endpoints.py`: 9 SKIP, exit 0, data file restored. Protected files
(`paper_engine.py`, `paper_market.py`, `routes/paper.py`, scenarios) and P4's `indicators.py`, `explain.py`,
`routes/analysis.py` unchanged.
