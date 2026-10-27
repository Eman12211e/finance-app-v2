# P4 Step 6 — educational explanations: final text for owner approval

Status: **final text for approval, not implemented.** Reviewed for consistency with the code, mathematical accuracy and
wording that could read as a prediction or a recommendation (changes from the first draft are listed at the end).
Example numbers were recomputed with `services/indicators.py` (synthetic-b, SYN-TEC1, day 161, Thu 14 Aug 2025).

## Behaviour (owner-approved)

- One card per active indicator, under the chart, in the order chosen (price lines first, then panes).
- **Card heading:** name, period and line style:
  - "SMA 20 (solid line)", "EMA 12 (dashed line)": the first price line is solid, the second dashed;
  - "RSI 14 (line in the RSI pane, guides at 30 and 70)";
  - "MACD 12-26-9 (MACD solid line, signal dashed line, histogram bars)".
  Each heading also carries the Simulated mark.
- **Shown by default:** the current reading (templates below), from the values the analysis API returned for the
  last completed bar. The browser only compares numbers (above, below, equal); it calculates nothing.
- **Learn more** (closed by default) reveals "What it shows", "How people read it" and "Watch out", labelled
  "Our plain summary".
- **What is this?** in the Indicators menu opens the complete explanation (What it shows, How people read it, Watch
  out and the footer) without switching the indicator on.
- **Footer on every card and explanation:** "Education only. An indicator describes past simulated prices; it is not
  a recommendation to buy or sell."
- Text lives in `data/indicator_guide.json` (static, no AI, no network). Numbers are shown as on the chart: dollars to
  2 decimals for SMA and EMA, RSI to 1 decimal, MACD to 2 decimals.

## Shared sentences

- **Weekly prefix** (weekly view only, before the reading): "On the weekly view (completed weeks only):"
- **Not enough data:** "{Name} needs {needed} {daily closes | completed weeks}. This view has {have} so far, so it is
  not drawn yet."
  Needed: SMA 20 → 20, SMA 50 → 50, EMA 12 → 12, EMA 26 → 26, RSI 14 → 15, MACD line → 26, MACD signal → 34.
- **Partial Week** (weekly, last bar unfinished), added after the reading: "This week is a Partial Week: it is shown
  on the chart but not used in any weekly value until it completes."
- **Final Short Week** (weekly, scenario's final day), added after the reading: "The last week is the scenario's Final
  Short Week ({days} trading days); it is complete and included."

## SMA 20 / SMA 50

**Current reading** ({unit} = day, or week on the weekly view; close = the last completed bar's close):
- above: "The latest close, ${close}, is above its {n}-{unit} average of ${value}."
- below: "The latest close, ${close}, is below its {n}-{unit} average of ${value}."
- equal to the cent: "The latest close, ${close}, is at its {n}-{unit} average."

**What it shows:** The average of the last {n} closing prices: the last {n} simulated days on the daily view, or the
last {n} completed weeks on the weekly view. Each new close replaces the oldest one in the average, which smooths out
day-to-day ups and downs.

**How people read it:** Some people look at whether the price is above or below the average, and at whether a
shorter average crosses a longer one. When the average has been rising, closes over that period have generally been
moving up.

**Watch out:** It uses only past prices, so it always lags behind them. It does not tell you what the next price will
be, and prices often cross back and forth over an average.

## EMA 12 / EMA 26

**Current reading:** as SMA, with "its {n}-{unit} EMA of ${value}" / "its {n}-{unit} EMA".

**What it shows:** An average of past closing prices in which recent closes count more than older ones, so it
responds sooner when prices change direction. It starts from the simple average of the first {n} closes; after that,
each new close moves it by a fixed share, 2 ÷ ({n} + 1).

**How people read it:** Some people compare a faster average, such as EMA 12, with a slower one, such as EMA 26 or
SMA 50, to see whether recent prices are moving away from the longer-run average.

**Watch out:** Responding sooner also means more false turns when prices move up and down without a clear direction.
Like every average, it describes the past.

## RSI 14

**Current reading** (value = RSI at the last completed bar, 1 decimal):
- 70 or above: "RSI is {value}: at or above 70, a level some people call "overbought". Recently, average gains have
  been more than twice the size of average losses."
- 30 or below: "RSI is {value}: at or below 30, a level some people call "oversold". Recently, average losses have
  been more than twice the size of average gains."
- above 50 and below 70: "RSI is {value}, between 30 and 70. Recently, average gains have been larger than average
  losses."
- above 30 and below 50: "RSI is {value}, between 30 and 70. Recently, average losses have been larger than average
  gains."
- exactly 50.0: "RSI is 50.0: recently, average gains and average losses have been the same size. RSI is also 50
  when prices have not moved at all."
- weekly: "Recently" stays; the pane uses completed weeks.

**What it shows:** The Relative Strength Index compares the average size of recent gains with the average size of
recent losses and puts the result on a scale from 0 to 100. It uses Wilder's smoothing over 14 periods, so the last
14 days (or completed weeks) count most and older moves fade gradually. 50 means average gains and losses are the
same size. The pane's dashed lines mark 30 and 70.

**How people read it:** Readings at or above 70 are often called "overbought", and at or below 30 "oversold". Those
labels describe how one-sided recent moves have been.

**Watch out:** Prices can stay above 70 or below 30 for a long time. A high reading does not mean prices are about to
drop, and a low one does not mean they are about to climb. It needs 15 closes before it shows a value.

## MACD 12-26-9

**Current reading** (MACD line, signal and histogram at the last completed bar; "previous" = the bar before it):
1. "The MACD line is {macd}: {above | below | at} zero, so the 12-{unit} EMA is {above | below | equal to} the
   26-{unit} EMA."
2. Signal line, one of:
   - "It is {above | below | level with} its signal line ({signal})."
   - (signal not available yet) "Its signal line needs 34 {daily closes | completed weeks}: Not enough data yet."
3. Change since the previous bar (only when both bars have a histogram value), one of:
   - same side, bigger gap: "The gap between them widened since the previous {unit}."
   - same side, smaller gap: "The gap between them narrowed since the previous {unit}."
   - opposite sides: "The MACD line crossed its signal line since the previous {unit}."
   - no change: "The gap between them did not change since the previous {unit}."

**What it shows:** MACD (Moving Average Convergence Divergence) has three parts. The MACD line is the 12-period EMA
minus the 26-period EMA. The signal line is a 9-period EMA of the MACD line. The histogram bars show the MACD line
minus the signal line. The dotted line marks zero.

**How people read it:** Above zero means the shorter average is above the longer one; below zero means it is under
it. Some people watch for the MACD line crossing its signal line or crossing zero.

**Watch out:** Crossings happen often and many reverse soon after. Because every part is built from averages, it
reacts after prices have already moved. The line needs 26 closes and the signal line 34.

## Words the guide must never use (a test will enforce this)

"you should", "buy now", "sell now", "buy signal", "sell signal", "guaranteed", "sure thing", "will rise",
"will fall", "time to buy", "time to sell", "bullish", "bearish", "we recommend", "I recommend", "best time".
The footer's "not a recommendation" is allowed. "Overbought" and "oversold" appear only as labels "some people"
use, always with the Watch out text.

## Examples (verified with `services/indicators.py`; SYN-TEC1, day 161, Thu 14 Aug 2025)

- SMA 20 (daily): "The latest close, $199.96, is above its 20-day average of $189.99."
- EMA 12 (daily): "The latest close, $199.96, is above its 12-day EMA of $188.90."
- RSI 14 (daily): "RSI is 56.1, between 30 and 70. Recently, average gains have been larger than average losses."
- MACD (daily): "The MACD line is -3.75: below zero, so the 12-day EMA is below the 26-day EMA. It is above its signal
  line (-5.81). The gap between them widened since the previous day." (histogram 1.15 → 2.06)
- MACD (weekly): "On the weekly view (completed weeks only): The MACD line is 13.41: above zero, so the 12-week EMA is
  above the 26-week EMA. Its signal line needs 34 completed weeks: Not enough data yet. This week is a Partial Week:
  it is shown on the chart but not used in any weekly value until it completes."
- Not enough data (SMA 50, daily, day 41): "SMA 50 needs 50 daily closes. This view has 41 so far, so it is not drawn
  yet."

## Changes from the first draft

1. RSI no longer says "over the last 14 days" (Wilder's smoothing weights them most but keeps older moves). The
   explanation now says so.
2. RSI zone sentences are exact: RSI 70 means average gains are 2.33 times average losses, so "more than twice" holds
   at and above 70 (and at and below 30 for losses). The middle zone says "larger", not "a little larger".
3. The flat-prices special case is dropped (telling it apart from equal gains and losses would need calculation in
   the browser); the RSI 50 sentence covers it.
4. MACD's change sentence now covers a crossing and no change, not only widened or narrowed.
5. "People watch for…" became "Some people…"; EMA's "longer trend" became "longer-run average".
6. Headings include the line style for every indicator (owner decision), and What is this? shows the complete
   explanation.
