# P5 progress log — Test a strategy

Read this first after any context reset. Brief and decisions: `docs/P5_BRIEF.md`. Base: `dev/v2` at `e929096` (P4).

| Commit | Step |
|---|---|
| `2e5d909` | 0: brief, owner decisions D1–D12, day numbering, start and entry rules |
| `f3e2c3c` | 1: mockups 09–11 (approved); warm-up Days 1–50 kept apart from evaluation |
| `b13d641` | 2: `services/backtest.py` + tests (for mathematical review) |
| `2e8b931` | 2 corrections + 3: exact signals, price checks, metrics, comparison, halves (for mathematical review) |
| `8cc6be6` | 3b: metrics reference at window ends covering every residue |
| `6a363c1` | 4: `POST /api/backtest/run`, API contract, validation and fuzz tests |
| this commit | 5 (draft): `docs/P5_CONTENT.md` for owner review; brief import line corrected; route body helper made local |

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

## Step 2 corrections (owner's review of `b13d641`)

1. **Unaffordable entry:** skipped, never borrowed, recorded in `skipped` with `code: "cash_below_one_share"` and the
   reason sentence. A rule that signals again later may enter then; buy and hold decides only on its start day, so a
   skipped benchmark stays in cash (tested both ways).
2. **Halves restart independently** (see step 3): each half is its own `simulate()` from $10,000.00 and no shares at
   the close of its own start day; earlier prices feed only the signals.
3. **Exact decisions:** `signals(closes)` replaces the float comparisons; the engine no longer imports
   `services.indicators` (the chart lines in step 4 still will). Definitions are the shared indicator's:
   - SMA 20 above SMA 50 ⇔ `sum20 / 20 > sum50 / 50` ⇔ `5·sum20 > 2·sum50` (integer prefix sums).
   - Wilder RSI: `g_14 = G / 14`, `g_i = (13·g_(i−1) + gain_i) / 14`. With `g_i = A_i / 14^(i−13)`:
     `A_14 = G`, `A_i = 13·A_(i−1) + gain_i·14^(i−14)` (substitute and multiply by 14^(i−13)); losses `B_i` share the
     denominator, so `g/l = A/B`. `RSI = 100 − 100/(1 + A/B)`: `< 30 ⇔ 7A < 3B`, `> 70 ⇔ 3A > 7B`; `B = 0` gives 50
     (A = 0, "mid") or 100 (A > 0, "high"), the shared convention. Exactly 30 or 70 does nothing.
   - Verified equal to the exact Fraction recursion and to the float indicator's classification on every day of every
     symbol, on 200 random small-move series, and at RSI exactly 30 / 70 and one cent either side, and SMA exactly
     equal and one cent either side. A searched-for case where RSI is exactly 30 but the float reads
     29.999999999999986 (a false buy for a float comparison) gives no signal. SMA floats cannot flip for whole-cent
     closes (equal sums divide to equal floats; distinct ones differ by ≥ 0.01 cent), and the tests show they agree.
4. **Invalid prices:** `simulate` refuses any open or close that is not a positive whole number of cents (bools
   included), naming the bar; `fill_price` refuses a result below 1 cent (a 1-cent open sold with example costs)
   instead of filling at zero.

## Step 3 — Metrics, comparison, halves

- **`metrics(sim)`** from the integer daily values v_S..v_L (n = L − S changes):
  - total return `(v_L − 1,000,000) / 1,000,000`;
  - max drawdown: largest `(peak − v_t) / peak` against the running peak, compared as exact fractions; ties keep the
    earliest trough; the peak is the first day its value was reached; `max_drawdown` gives peak and trough
    {index, date, value_cents}, or null when the value never fell below a previous peak;
  - daily volatility: sample standard deviation (n − 1) of the exact `v_t / v_(t−1) − 1`, not annualised; the variance
    is an exact fraction and `sqrt_pct` rounds its square root exactly in integers (`isqrt`), no float step;
  - buys, sells, `evaluation_days` = n, `days_invested` (days t in S+1..L ending with shares), costs paid in cents.
  - Percentages round half away from zero to two decimals from exact fractions (`pct`); never "-0.0".
- **`compare(dates, bars, rule, costs, start)`**: rule and buy and hold on identical days from identical starts, each
  with `metrics`; `difference_pp` from the exact final values, `(v_L^rule − v_L^b&h) / 10,000`, then rounded. It can
  differ by 0.01 from subtracting the two rounded returns (tested bound); the UI should show this number, not
  recompute it.
- **`halves(...)`**: null unless L − S ≥ 80; `M = S + ⌊(L − S) / 2⌋`; earlier = `compare` on bars up to M from S
  (identical to the full run's prefix, as it shares S); later = `compare` on all bars from M, restarted with fresh
  cash and no shares, no inherited position or trades. A cross between M − 1 and M is a decision made on M and is
  acted on; averages already apart at M are not an entry. Descriptive only: nothing is fitted, nothing is called
  in-sample or out-of-sample.
- **`run()`** returns `result = compare(..., 49)` plus `halves`.

**Conventions to review:** rounding half away from zero; drawdown tie → earliest trough, peak's first day;
volatility of daily value changes including cash days (0% moves lower it, as the brief's explanation says);
`difference_pp` from exact values; later half restarted at M with a crossing on M counted.

**Checks:** pytest 785 passed (679 before; `tests/test_backtest.py` now 225):

- `ref_metrics`: brute-force drawdown over every pair of days, 60-digit `Decimal` returns, variance, square root and
  `ROUND_HALF_UP`, equal to `metrics()` for every symbol, rule and cost setting at four window ends and on every half;
  volatility also within 0.005 of `statistics.stdev` on floats;
- hand-worked series (returns, tied drawdowns, days invested, 13.77% volatility), flat and rising series, rounding at
  exactly half a hundredth in both signs, the square root exactly at, just below and just above a rounding boundary;
- the approved mockup 09 numbers (SYN-HLT1, Day 161): +4.43% / +10.30%, −5.87 points, drawdowns 10.51% / 10.73% with
  dates, volatility 0.96% / 1.63%, 49 of 111 days, costs $30.91 / $10.89, halves −1.75% / +2.86% and +9.14% / +7.18%;
- halves: none at L = 128, shown at L = 129 (40 + 40), never on synthetic-a; each half of every long symbol, rule
  and cost setting starts at $10,000.00 and no shares, equals the exact reference run from its own start and passes
  the accounting replay; the earlier half equals the full run's prefix; a cross on M is acted on; a position held by
  the full run at M is not inherited; later prices change nothing earlier in a later-start run; repeat runs identical.

Mutation checks (one at a time, file restored byte for byte, all 12 caught): drawdown from the start value, peak dated
on its latest day, population standard deviation, later half not restarted, non-strict SMA, non-strict RSI 30, wrong
RSI recurrence scale, fill-price guard dropped, price validation dropped, rounding at a third, square-root rounding off
by half, difference from rounded returns.

**Reproduce** (no CI in this repo; from the repo root, any Python 3.12 with pytest):

    python -m pytest -q -p no:cacheprovider               # 785 passed
    python -m pytest tests/test_backtest.py -q             # 225 passed
    python scripts/check_endpoints.py; echo $?             # 9 SKIP (no keys), exit 0
    git checkout -- data/endpoint_check.json               # the check rewrites this file

**Limitations:** volatility and returns are display-rounded floats beside exact cents and indices; all checks run on
the two fixed synthetic markets plus hand-made series; the brief's §5 line "imports only services.indicators" is now
"imports only the standard library" (the brief itself is unchanged).

## Step 4 — `POST /api/backtest/run`

- **`routes/backtest.py`** (new blueprint, registered in `app.py`): body exactly {state, symbol, preset, costs};
  unknown fields, non-string or unknown preset / cost setting / symbol give `INVALID_REQUEST`; a missing, malformed or
  tampered session gives `INVALID_STATE` (from `paper_engine.market_bars`, the only engine function used); over 64 KB
  gives 413 (the app-wide limit, via P4's `_body`); anything unexpected is logged and answered `INTERNAL_ERROR` with
  no details. Bars stop at the session's day, so L is always today. The response (documented in
  `docs/API_CONTRACT.md`, "Test a strategy") carries both sides' values, fills, skipped entries, end position and
  metrics, `difference_pp`, `unacted_signal`, halves (metrics and fills, no daily values), the session dates and the
  rule's own indicator lines in P4 display units, the scenario notice and the brief's standing note. Not enough
  history gives `result: null` with `needed_days` and `available_days`.
- It never writes: the engine's state-changing functions are stubbed to fail in a test, the posted state is compared
  before and after, and a session holding a practice position gets the same result as one without (the test uses
  its own fictional $10,000).
- **`tests/test_backtest_api.py`** (72): the mockup request's numbers and shape; every symbol of both markets × both
  rules × both cost settings at three session days equal to the independent reference (fills, skipped, values,
  metrics, unacted signal, later half); RSI line; not enough history at days 1, 2, 50, 69 and the first result at
  70; halves at 129 / 130; nothing after the session day used or returned; a signal on the current day; byte-identical
  repeat responses; tampered, malformed and missing sessions; read-only; body not an object; 64 KB; GET refused;
  unknown fields, symbols (including the other market's), presets and cost settings with bools, numbers, lists and
  objects; a seeded fuzz of 400 malformed bodies (only 200 / 400, reaching OK, INVALID_REQUEST and INVALID_STATE); an
  unexpected failure answered without details; the route calls only `paper_engine.market_bars`.
- Route mutation checks: unknown fields accepted, no type check on costs, a full-scenario read instead of the
  session's days, the benchmark swapped for the strategy, and errors re-raised are each caught. Dropping the type
  check on the preset is an equivalent mutant (membership in a tuple of strings cannot raise or accept a non-string),
  kept for clarity.
- Audit run once (not in the suite, ~3 minutes): engine, metrics and accounting against the reference at **every**
  last day for every symbol, rule and cost setting (13,644 runs) and the halves at every third last day from 129
  (7,872 half runs): 0 mismatches. Evidence: `..\finance-app-v2-screenshots\P5\step-3-4\`.

**Checks:** pytest 858 passed (785 + 1 in 3b + 72); `check_endpoints.py` 9 SKIP, exit 0, data file restored;
protected and P4 files unchanged since `e929096`.

## Owner review of steps 3–4 (2026-11-02)

Approved conventions: the points difference from exact values, rounded once; a crossing on the later half's first day
counts when earlier prices establish it; each half restarts with $10,000.00, no shares and no inherited trades.

- `docs/P5_BRIEF.md` sections 2, 3.7 and 5 now say the engine imports only the standard library and decides with exact
  integer forms of the `services.indicators` definitions (the route uses `services.indicators` for chart lines only).
- `routes/backtest.py` no longer imports P4's private `_body` from `routes/analysis.py`: every route in the codebase
  keeps its own copy (paper, analysis), and a shared module would mean editing protected files, so the same seven
  lines are local. Behaviour unchanged (body, 413 and fuzz tests pass).

## Step 5 (draft) — `docs/P5_CONTENT.md`

Every explanation, result sentence and state for owner review; not implemented (no guide JSON, endpoint or UI).
Example numbers are computed by the engine. Two mockup sentences were found wrong while checking and are corrected in
the draft: SYN-HLT1's averages crossed 4 times, not 3 (the rule acted on 3), and SYN-TEC1's averages did cross (down,
Day 141, while in cash). "Typical daily move" is proposed as "Daily volatility" with a standard-deviation sentence.

**Checks:** pytest 858 passed; `check_endpoints.py` 9 SKIP, exit 0, data file restored.
