# P4 Step 6 — educational explanations: content draft for owner review

Status: **draft, not implemented.** Nothing here is wired into the app until the owner approves the wording.
Approved behaviour this draft follows (`docs/P4_BRIEF.md`, mockup-gate decisions 2 and 5): one card per active
indicator below the chart, showing the short current reading by default with a **Learn more** control for the rest;
**What is this?** opens an indicator's explanation without switching it on.

## How the cards will work (for review)

- One card per active indicator, in the order chosen (lines first, then panes), under the chart's legend.
- Card heading: the indicator's name and its line style where it has one ("SMA 20, solid line"), plus the Simulated
  mark. First line: the **current reading** (templates below), built only from the values the analysis API returned
  for the last completed bar. No new maths in the browser: comparisons only (above, below, between).
- **Learn more** (a `<details>` disclosure, closed by default) reveals "What it shows", "How people read it" and
  "Watch out", labelled "Our plain summary" (written for this app, as in Understand Before You Sign).
- Footer on every card: "Education only. An indicator describes past simulated prices; it is not a recommendation to
  buy or sell."
- **What is this?** links in the Indicators menu, one per preset: they open the same Learn more text in a small panel
  inside the menu (desktop popover or phone sheet), without switching the indicator on.
- Content lives in `data/indicator_guide.json` (static; served with the page, no AI, no network). The reading
  sentences are templates filled with the API's numbers.
- Tests (step 6 implementation): every preset has a guide entry with all four parts; no advice or prediction wording
  (list below) anywhere in the guide or the templates; every template has a "Not enough data" and a "Partial Week"
  branch; the cards never call the API for anything except the chart request already made.

## Words the guide must never use

"you should", "buy now", "sell now", "buy signal", "sell signal", "guaranteed", "sure thing", "will rise",
"will fall", "time to buy", "time to sell", "bullish", "bearish", "we recommend", "I recommend", "best time". A test
will reject them (the footer's "not a recommendation" is allowed).

## Shared wording

- **Not enough data:** "{Name} needs {needed} {daily closes | completed weeks}. This view has {have}, so nothing is
  drawn yet." (needed: SMA 20 → 20, SMA 50 → 50, EMA 12 → 12, EMA 26 → 26, RSI 14 → 15, MACD line → 26, MACD signal
  → 34.)
- **Weekly view:** reading sentences start with "On the weekly view, using completed weeks only, ...".
- **Partial Week** (weekly, last bar unfinished): one extra sentence on each card: "This week is a Partial Week: it is
  shown on the chart but not used until it completes."
- **Final Short Week:** "The last week is the scenario's Final Short Week ({days} trading days); it counts as
  completed."

## SMA (20 or 50)

**Current reading** (close = last completed bar's close, value = SMA at that bar):
- close above value: "The close of ${close} is above its {n}-day average of ${value}."
- close below value: "The close of ${close} is below its {n}-day average of ${value}."
- equal (to the cent): "The close of ${close} is at its {n}-day average."
- (weekly: "{n}-week average")

**What it shows:** The average closing price over the last {n} simulated days (or completed weeks). It smooths out
day-to-day ups and downs so the general direction is easier to see.

**How people read it:** Some people look at whether the price is above or below the average, or at whether a shorter
average crosses a longer one. A rising average means recent closes have been higher than older ones.

**Watch out:** It is built only from past prices, so it always lags behind. It does not tell you what the next price
will be, and prices often cross back and forth over an average.

## EMA (12 or 26)

**Current reading:** as SMA, with "its {n}-day EMA of ${value}" (weekly: "{n}-week EMA").

**What it shows:** An average where recent days count more than older ones, so it reacts sooner when prices change
direction. The first value starts from a simple average of the first {n} closes.

**How people read it:** People often compare a faster EMA with a slower average to see whether recent prices are
moving away from the longer trend.

**Watch out:** Reacting sooner also means more false turns when prices bounce around. Like every average, it describes
the past.

## RSI 14

**Current reading** (value = RSI at the last completed bar):
- 70 or above: "RSI is {value}: above 70, a level some people call \"overbought\". Recent gains have been much larger
  than recent losses."
- 30 or below: "RSI is {value}: below 30, a level some people call \"oversold\". Recent losses have been much larger
  than recent gains."
- between, 50 or above: "RSI is {value}, between 30 and 70. Over the last 14 {days | weeks}, gains have been a little
  larger than losses."
- between, below 50: "RSI is {value}, between 30 and 70. Over the last 14 {days | weeks}, losses have been a little
  larger than gains."
- exactly 50 because nothing moved (flat prices): "RSI is 50: prices did not move, so there were no gains or losses."
  (shown only when the API returns 50 and the last 15 closes are equal; the current markets never do this)

**What it shows:** Compares the size of recent gains with recent losses on a scale from 0 to 100, using the last 14
{days | completed weeks}. The pane's dashed lines mark 30 and 70.

**How people read it:** Readings above 70 are often called "overbought" and below 30 "oversold": recent moves have
been one-sided.

**Watch out:** Prices can stay above 70 or below 30 for a long time. A high reading does not mean prices are about to
drop, and a low one does not mean they are about to climb.

## MACD 12-26-9

**Current reading** (MACD, signal and histogram at the last completed bar; previous = the bar before it):
- line: "MACD ({macd}) is {above | below} zero" + signal part + histogram part:
  - signal part: "and {above | below} its signal line ({signal})" — or "; its signal line is Not enough data yet"
  - histogram part (both bars have a histogram): ", and the gap {widened | narrowed} since the previous
    {day | week}." — or nothing when the previous bar has none.
- "Above zero means the 12-{day|week} EMA is above the 26-{day|week} EMA; below zero means it is under it."

**What it shows:** The difference between a 12-day and a 26-day EMA (the MACD line), with a 9-day EMA of that
difference (the signal line). The bars show the gap between the two lines; the dotted line is zero.

**How people read it:** Below zero means the shorter average is under the longer one. People watch for the MACD line
crossing its signal line or crossing zero.

**Watch out:** Crossings are frequent and many reverse soon after. Because it is built from averages, it reacts after
prices have already moved.

## Examples with real values (synthetic-b, SYN-TEC1, day 161, Thu 14 Aug 2025)

- Daily SMA 20: "The close of $199.96 is above its 20-day average of $189.99."
- Daily RSI 14: "RSI is 56.1, between 30 and 70. Over the last 14 days, gains have been a little larger than losses."
- Daily MACD: "MACD (-3.75) is below zero and above its signal line (-5.81), and the gap widened since the previous day."
- Weekly MACD: "On the weekly view, using completed weeks only, MACD (13.41) is above zero; its signal line is Not
  enough data yet. This week is a Partial Week: it is shown on the chart but not used until it completes."

## Questions for the owner

1. Approve, edit or reject each block of wording above (reading templates, Learn more parts, shared lines).
2. Should the "What is this?" panel in the menu show the full Learn more text, or only "What it shows" with a link to
   the card?
3. Should the card mention the indicator's line style ("solid line" / "dashed line") in its heading, as drafted?
