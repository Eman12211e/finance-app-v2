# P5 Step 5 — Test a strategy: educational text for owner approval

Status: **draft for owner review, not implemented.** Nothing here is wired into the app yet. After approval it is
copied word for word into `data/strategy_guide.json`, served by `GET /api/backtest/guide` and used by the result
sentences and explanation cards in steps 6–8. A test then checks that the two match.

Checked against `docs/P5_BRIEF.md` (sections 3 and 4, owner decisions D1–D12, the approved conventions of
2026-11-02) and against the working engine and API (`services/backtest.py`, `POST /api/backtest/run`). Every example
number below was produced by the engine, not copied from the mockups. Changes from the wording in mockups 09–11 are
listed at the end.

## Behaviour (as the brief and mockups)

- **Result sentences** are filled from the API's numbers; the browser compares and formats numbers only and works
  nothing out. Money is dollars and cents ($10,442.81). Returns are signed with two decimals (+4.43%, −1.75%, 0.00%).
  Days are numbered from 1 (the API's index + 1); dates are short (May 12).
- **Explanation cards** (under the results, as P4): a heading, a one-sentence reading from this run, and **Learn more**
  (closed by default) with the parts below, labelled "Our plain summary". **What is this?** next to each rule in the
  setup form opens the rule's full explanation without running anything.
- **Simulated** label on the result heading and on every card. The **standing note** ends every result.
- **Past tense only** in anything that describes a result. No ranking of rules, no "better" or "worse".

## Standing text

- **Result label:** "Simulated: hypothetical results on synthetic prices"
- **Standing note (every result, from the brief):** "This is a hypothetical test on computer-generated prices. A rule
  that did well here can do badly on other prices. Past results, real or simulated, do not tell you what will happen
  next."
- **Card footer:** "Education only. This describes a test on past simulated prices; it is not a recommendation to
  buy or sell."
- **Setup form intro:** "Replay a fixed rule on the days you have reached, next to buying and holding the same
  ticker."
- **Setup form footnote:** "Uses Days 1–{today}. Your practice account is not changed."

## Why this is not a forecast

(Shown under How this test works, and in the guide.)

A backtest replays a fixed rule on prices that have already happened and reports what that rule would have done. It
cannot show what the rule would do on prices that have not happened yet. These prices were made by a computer
program, and even with real prices the past is only one of many ways things could have gone. A rule can look good
because it happened to suit this particular stretch of prices. The rules here use textbook settings chosen before
any of these prices existed, and nothing is adjusted to make them fit, but a fixed rule is still only being tested on
one set of prices.

## The rules

### SMA crossover 20 / 50

- **Setup line:** "Buys when the 20-day average crosses above the 50-day average; sells when it crosses back below."
- **Card reading:** one of:
  - "The rule acted on {n} crossings: {up} up through the 50-day average and {down} back down." (n = buy and sell
    signals: fills, skipped entries and a last-day signal; "1 crossing", "1 up", "0 back down" as needed)
  - with no signal at all: "The 20-day average never crossed above the 50-day average while the rule was in cash, so
    it never bought."
  It counts crossings the rule acted on, not every crossing: one that happens while the rule is already in the
  position it points to (for example a cross down while in cash) changes nothing and is not counted.
- **What it does:** It starts in cash. After each day's close it compares two averages of closing prices: the last
  20 days and the last 50 days. When the 20-day average moves from at-or-below the 50-day average to above it, the
  rule buys at the next day's open. When the 20-day average moves from above back to at-or-below, it sells everything
  at the next day's open. Equal averages count as "not above".
- **Why people test it:** It is a simple way to follow a trend: be in while recent prices are above longer-run
  prices, and step out when they are not.
- **Watch out:** Averages lag, so it enters and leaves after a move has already started. When prices go up and down
  without a clear direction, it can buy after a rise and sell after a fall again and again, paying costs each time.
- **Starting rule (in How this test works):** The test starts in cash and waits for a fresh crossing. If the 20-day
  average is already above the 50-day average on Day 50, that is not treated as a buy that happened earlier. The
  first crossing the test can see is on Day 51, so its first fill can be at the Day 52 open.

### RSI 14 below 30 / above 70

- **Setup line:** "Buys when RSI 14 closes below 30; sells when it closes above 70."
- **Card reading:** one of:
  - "The rule acted on {n} RSI readings: {low} below 30 while in cash and {high} above 70 while holding." (n = buy
    and sell signals: fills, skipped entries and a last-day signal; singular forms as needed)
  - with no signal at all: "RSI 14 never closed below 30 while the rule was in cash, so it never bought."
- **What it does:** It starts in cash. While in cash, it buys at the next day's open when RSI 14 closes below 30.
  While holding shares, it sells everything at the next day's open when RSI 14 closes above 70. A close of exactly 30
  or exactly 70 does nothing.
- **Why people test it:** It tries the opposite of following a trend: buying after a run of losses and selling after
  a run of gains.
- **Watch out:** RSI can stay below 30 while prices keep falling, and after a buy it may not close above 70 again for
  a long time, so the rule can hold through a long decline. Between 30 and 70 it does nothing at all.
- **Starting rule (in How this test works):** RSI 14 already has values on Day 50. If it closed below 30 that day,
  the rule buys at the Day 51 open, the same day buy and hold buys. This rule could start sooner, but it uses the
  same Day 50 start as the crossover rule so every test covers the same days.

### Buy and hold (the benchmark)

- **Shown with every test, never chosen on its own.**
- **Card reading:** "Buy and hold bought {shares} shares at the Day 51 open (${open}, fill price ${price}) and kept
  them."
- **What it does:** It buys as many whole shares as $10,000 allows at the first opening price after the start (Day
  51) and never sells.
- **Why it is here:** It answers "what if I had bought this ticker and done nothing?" over exactly the same days,
  with the same costs. A rule's result means more next to it than on its own.
- **Watch out:** It is a point of comparison, not a target. Over a different stretch of prices buy and hold can do
  very differently, and so can the rule.

## How this test works

(Five short points, as in mockup 09, plus "Why this is not a forecast" above.)

1. **Timing:** "Decisions are made after each day's close, using only prices up to that day. They fill at the next
   day's opening price, the same rule as your practice orders. The opening price can be different from the close the
   decision was based on, sometimes by a lot."
2. **Money:** "It starts with $10,000.00 in cash and buys as many whole shares as the cash allows, then sells all of
   them on the way out. It never borrows, so cash never goes below zero. Cash left over after buying whole shares
   stays as cash."
3. **Costs (one of):**
   - Example costs: "Example costs: each fill is 0.10% worse than the opening price: a buy pays 0.10% more and a sell
     receives 0.10% less, rounded to the cent against the trader. No commission."
   - No costs: "No costs: every fill is at the opening price exactly. Real trading usually has some cost."
4. **Warm-up:** "Days 1–50 are price history used only to build the 50-day average. Nothing is invested and no return
   is counted for them; the test and buy and hold both start at the Day 50 close."
5. **Your session:** "Only days you have reached in Practice Trading are used. Your practice account, orders and cash
   are not changed."

### Trading costs and slippage (Learn more under point 3)

- **What it shows:** Slippage is the gap between the price you see and the price you actually get. Here it is a
  fixed example: every fill is 0.10% worse than that day's opening price. On a $100.00 open, a buy fills at $100.10
  and a sell at $99.90. "Costs paid" adds up that gap over every fill.
- **Watch out:** Costs change more than the costs line. A buy at a higher price can mean one fewer whole share, so the
  final value can move by more or less than the costs paid. Real costs vary from trade to trade and can be larger
  than this example.

## Results

### Outcome sentence (top of the results)

- "This rule ended at ${end} ({return}). Buying and holding {symbol} over the same days ended at ${bh_end}
  ({bh_return}), so the rule ended {points} points {higher | lower}."
- Equal to the hundredth: "…, so the rule ended level with buying and holding (0.00 points)."
- **Window line (above it):** "Results are measured from the Day 50 close ({date}), when both start with $10,000.00
  in cash, to the Day {last} close ({date}): {days} trading days. Days 1–50 are price history used only to build the
  50-day average; nothing is invested and no return is counted for them. {Example costs | No costs}."

### Metrics table

Columns "This rule" and "Buy and hold"; rows in this order. Each row has a card.

| Row | Cell | Card reading |
|---|---|---|
| Value at the end | $10,442.81 | (none) |
| Total return | +4.43% | "The $10,000 became ${end}, a change of {return}." |
| Largest drop from a high | −10.51%, "May 12 to Jun 9" (or "No drop") | see below |
| Daily volatility | 0.96% | "The value's daily changes had a standard deviation of {vol}." |
| Trades | "2 buys, 1 sell" | "The rule bought {buys} times and sold {sells} times." |
| Days invested | "49 of 111" | "Shares were held at the close on {n} of {days} test days ({pct})." |
| Costs paid | $30.91 | "The example costs added up to ${costs} across {fills} fills." / "No costs were charged." |
| Compared with buy and hold | "5.87 points lower total return" | (the outcome sentence) |

**Total return**

- **What it shows:** How much the $10,000 grew or shrank from the Day 50 close to the last close, after the costs
  chosen: (value at the end − $10,000) ÷ $10,000. Shares still held at the end are valued at the last close; they are
  not sold and no further cost is charged.
- **Watch out:** One number for the whole stretch hides how bumpy it was along the way. Read it with the largest drop
  and daily volatility.

**Compared with buy and hold (percentage points)**

- **What it shows:** The rule's total return minus buy and hold's, in percentage points. +4.43% against +10.30% is
  5.87 points lower: a difference between two percentages, not "57% lower".
- **How it is worked out:** From the exact end values, then rounded once, so it can differ by 0.01 from subtracting
  the two rounded returns shown above it.
- **Watch out:** It compares two results on the same synthetic days. It says nothing about which would do
  differently on other prices.

**Largest drop from a high (maximum drawdown)**

- **Card reading:** "The value fell {pct} from its high on {peak date} to a low on {trough date}." If the value never
  fell below an earlier high: "The value never fell below an earlier high on these days." If the rule never invested:
  "The value stayed at $10,000.00 in cash, so it never dropped."
- **What it shows:** The worst fall from a high point to a later low, measured on the value at each day's close, as a
  share of that high. It shows how uncomfortable the ride could have been, which the final number hides.
- **Watch out:** It only covers these days and closing values; moves during a day are not counted. A longer or
  different stretch can have a deeper drop. Recovering from a drop takes a bigger percentage gain than the drop
  itself: after a 10% fall, it takes about an 11% rise to get back.

**Daily volatility**

- **What it shows:** A measure of how much the value moved up or down from one close to the next: the standard
  deviation of the daily changes, in percent. A bigger number means a bumpier ride. It is for one day, not a year.
- **Watch out:** Days spent in cash move by 0%, which makes this number smaller without making the rule any safer.
  A low number does not mean a big drop cannot happen.

**Trades**

- **What it shows:** How often the rule acted: each buy and each sell is one fill, and each fill pays the cost
  setting. Buy and hold shows 1 buy and 0 sells.
- **Watch out:** More trades mean more costs. A count does not say whether the trades helped.

**Days invested**

- **What it shows:** On how many of the test days the rule ended the day holding shares, out of all the test days.
  The rest of the time the money sat in cash, earning nothing.
- **Watch out:** Time out of the market avoids some falls and also misses some rises.

**Costs paid**

- **What it shows:** The total of the 0.10% example cost over every fill, in dollars. With No costs it is $0.00.
- **Watch out:** See "Trading costs and slippage": the effect on the final value is not exactly this number.

### What the rule did (fills list)

- **Table headings:** Signal at the close of · Filled at the open of · Action · Shares · Open · Fill price · Cost ·
  Cash after. (Rendered as table columns, not a dotted line.)
- **Action words:** "In: bought" and "Out: sold" (In / Out, so they are not mistaken for your practice trades).
- **Open position at the end:** "Still holding {shares} shares at the end, valued at the Day {last} close of
  ${close}. They were not sold, so no further cost was charged."
- **Buy and hold line:** the benchmark card reading above.

### Earlier and later halves

- **Intro:** "The same rule, tested again on each half from a fresh $10,000."
- **Rows:** "Earlier half: Day 50 close to Day {mid} close ({date} – {date})" and "Later half: Day {mid} close to Day
  {last} close ({date} – {date})", with both returns.
- **How it works (Learn more):** Each half is a separate test that starts with $10,000.00 in cash and no shares at
  the close of its first day. Nothing carries over from the full test: no shares, no cash, no trades. The later half
  still uses the prices before it to build its averages, so a crossing on its first day counts as a signal, and an
  average that was already above the other on that day is not treated as an earlier buy.
- **Note under the table (always):** "This only describes what happened in two stretches of synthetic prices. It is
  not evidence that the rule works, and neither half tells you how the other, or any later stretch, will go."
- The words "in-sample" and "out-of-sample" are never used.

## States

- **Not enough data:** heading "Not enough data yet"; "This test needs 70 trading days of history: 50 to build the
  50-day average and at least 20 to test on. You have reached {available} so far." and "Advance {70 − available}
  more days in Practice Trading to run it. Nothing is estimated in the meantime." (Both rules need 70, so they always
  cover the same days.)
- **No trades** (shown when there are no fills, no skipped entries and no last-day signal; otherwise the fills list
  shows those lines): heading "No trades: the rule never triggered"; then for the crossover rule "The 20-day average
  did not cross above the 50-day average from the Day 50 close to Day {last}, so the rule stayed in cash at
  $10,000.00 (0.00%)."
  or for the RSI rule "RSI 14 never closed below 30 from the Day 50 close to Day {last}, so the rule stayed in cash at
  $10,000.00 (0.00%)."; then "Buying and holding {symbol} over the same days ended at ${bh_end} ({bh_return})." and,
  for the crossover rule, "The test starts in cash and waits for a fresh crossing. It does not assume a trade
  happened before the Day 50 close."
- **Skipped entry** (only possible when one share costs more than the cash; no synthetic ticker comes close): in the
  fills list, "Signal at the close of Day {n}: buy. Not filled: the cash did not cover one share at the Day {n + 1}
  fill price of ${price}. The money stayed in cash." For buy and hold: "Buy and hold could not afford one share at
  the Day 51 open (fill price ${price}), so it stayed in cash." Buy and hold only decides once, so it does not try
  again; a rule tries again at its next signal.
- **Signal on the last day:** "Signal on Day {last}, the last day so far: {buy | sell}. Not acted on, because there
  is no next open yet." (If you advance a day in Practice Trading and run the test again, it fills at that day's
  open.)
- **Too short to split:** "Too short to split: each half needs at least 40 test days, and there are {days} so far.
  Available from Day 130."
- **Request failed:** heading "The test could not run"; "The server did not answer. Your practice session is
  unchanged." Button "Try again". For a session that could not be verified, the app's existing message: "This
  practice session could not be verified. Reset to start a new one."
- **Running:** "Running {rule} on {symbol}." (button "Running test…").

## Words the text must never use (enforced by a test)

From the brief's wording rules and P4's list: "will" (except in the standing note and the halves note, where it
appears only as "will go" / "will happen next" in a sentence that says results do not tell you), "expect",
"predict", "best", "winning", "beat the market", "outperform", "guaranteed", "you should", "buy now", "sell now",
"sure thing", "buy signal", "sell signal", "time to buy", "time to sell", "bullish", "bearish", "we recommend",
"I recommend", "in-sample", "out-of-sample". Rules are never ranked or sorted by result.

## Examples (computed by `services/backtest.py`, synthetic market B)

- **SMA crossover, SYN-HLT1, Day 161, example costs:** "This rule ended at $10,442.81 (+4.43%). Buying and holding
  SYN-HLT1 over the same days ended at $11,029.60 (+10.30%), so the rule ended 5.87 points lower." Largest drop
  −10.51% (May 12 to Jun 9) / −10.73% (May 12 to Jul 3); daily volatility 0.96% / 1.63%; 2 buys, 1 sell / 1 buy, 0
  sells; 49 of 111 / 111 of 111 days; costs $30.91 / $10.89. Fills: Day 79 → Day 80 In: bought 94 at $105.69 (open
  $105.58, cost $10.34, cash after $65.14); Day 113 → Day 114 Out: sold 94 at $101.17; Day 146 → Day 147 In: bought
  93 at $102.01. "Still holding 93 shares at the end, valued at the Day 161 close of $111.34." "Buy and hold bought 99
  shares at the Day 51 open ($100.83, fill price $100.94) and kept them." Halves (midpoint Day 105): earlier −1.75% /
  +2.86%, later +9.14% / +7.18%.
- **The same with No costs:** $10,483.16 (+4.83%) against $11,040.49 (+10.40%), 5.57 points lower. The example costs
  paid $30.91 but left the rule $40.35 lower, partly because the third buy got 93 shares instead of 94.
- **SMA crossover card, SYN-HLT1, Day 161:** "The rule acted on 3 crossings: 2 up through the 50-day average and 1
  back down." (The averages crossed 4 times; the cross down on Day 64 came while the rule was in cash.)
- **No trades, SYN-TEC1, SMA crossover, Day 161:** "The 20-day average did not cross above the 50-day average from
  the Day 50 close to Day 161, so the rule stayed in cash at $10,000.00 (0.00%)." (It was already above on Day 50 and
  crossed down on Day 141, while in cash.) Buy and hold ended at $11,298.08 (+12.98%), 12.98 points lower; its largest
  drop was −29.93% (Jun 19 to Aug 5).
- **Signal on the last day, SYN-CON1, SMA crossover, Day 165:** "Signal on Day 165, the last day so far: sell. Not
  acted on, because there is no next open yet." Still holding 188 shares, valued at the Day 165 close of $45.75. The
  rule ended at $8,621.86 (−13.78%) against $10,068.20 (+0.68%), 14.46 points lower; its largest drop ends on the last
  day (May 8 to Aug 20).
- **RSI rule, SYN-ENR1, Day 161:** "This rule ended at $12,372.72 (+23.73%). Buying and holding SYN-ENR1 over the same
  days ended at $12,065.65 (+20.66%), so the rule ended 3.07 points higher." 1 buy (Day 57), 1 sell (Day 138); 81 of
  111 days. Halves: earlier +5.34% / −2.41%, later 0.00% / +23.03% (no trade in the later half). The same rule on the
  same ticker, very different in each half.
- **Not enough data, Day 41:** "This test needs 70 trading days of history: 50 to build the 50-day average and at
  least 20 to test on. You have reached 41 so far." "Advance 29 more days…"
- **Too short to split, SYN-HLT1, Day 100:** "…each half needs at least 40 test days, and there are 50 so far.
  Available from Day 130."

## Changes from the mockup wording

1. "Typical daily move" is renamed **Daily volatility**, and its reading now says "standard deviation" instead of "On
   a typical day the value moved about 0.96%". A standard deviation is not the size of a typical day's move (cash days
   at 0% pull it down, and it is not an average of moves), so the old sentence was not exact.
2. The drawdown reading says "to a low on {date}" (the old "from its high on May 12 to Jun 9" read as a date range).
3. Days invested says "held at the close", which is what is counted.
4. The points comparison explains percentage points and the 0.01 rounding difference (approved convention 1).
5. The halves explanation states the approved restart and first-day crossing conventions (2 and 3).
6. **Correction:** mockup 09's "The 20-day average crossed the 50-day average 3 times" was wrong for SYN-HLT1 (they
   crossed 4 times; the rule acted on 3), and mockup 11's "did not cross" was wrong for SYN-TEC1 (a cross down on Day
   141 while in cash). The rule cards now count only the crossings or readings the rule acted on, which the API
   reports exactly; "did not cross above" replaces "did not cross".
7. New: the costs explanation notes that costs can change the share count, with the SYN-HLT1 example.
8. New: "Why this is not a forecast", the rule-starting notes, the RSI rule's reasons for sharing the Day 50 start,
   skipped-entry wording, the no-trades sentence for the RSI rule, and the session-could-not-be-verified message.

## Step 6 addendum: interface sentences (approved by the owner 2026-11-02)

Added while building the setup and results view (step 6). Each is a plain status line with no claim about results;
they are in use.

- **Day changed:** "The practice day changed, so the previous result was cleared. Run the test again to include the
  new day." (A result only covers the day it ran on; Next day while the view is open clears it.)
- **Screen-reader announcement after a run** (in the polite status line, not shown on screen): "Test finished."
  followed by the outcome sentence; "Not enough data yet."; "The test could not run."
- **Metrics table footer when the difference is exactly 0.00:** "Level with buy and hold (0.00 points)".

## Step 7 addendum: chart text (approved by the owner 2026-11-02)

The chart's heading, readout, warm-up labels, legend and text version follow approved mockup 09 word for word. These
lines cover cases the mockup did not show; they are in use.

- **Text version, RSI rule:** "RSI 14 in a pane below the prices, with guides at 30 and 70;" (in place of the SMA
  sentence) and "price history for the indicator only" (in place of "for the averages only").
- **Text version, no fills:** "…the rule made no fills on these days."
- **Text version, skipped entry:** "Not filled marks an entry the cash did not cover."
- **Text version, last-day signal:** "A signal on the last day, not acted on, is marked on the last day."
- **Chart markers:** "Not filled" (a skipped entry) and "Signal, not acted on" (a decision on the last day), beside
  In and Out.
- **Library missing:** "The chart could not load." followed by the text version.

