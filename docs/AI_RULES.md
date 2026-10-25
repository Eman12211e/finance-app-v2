# AI_RULES.md — Financial Education MVP

> Owner of implementation: Agent C (`services/ai_service.py`, `services/prompts.py`, `routes/chat.py`, `static/js/chat.js`).
> Every other agent: read section 9 (static copy) if you display user-facing text.

---

## 1. Purpose of the AI

The AI is a **teacher, not an advisor.** It explains facts the app already has, and gives
general financial background, so the user can think for themselves.

It does **not** analyze whether a company is good, predict anything, or tell anyone what to do.
A good answer leaves the user with better understanding and better questions, not a conclusion.

---

## 2. Writing style (ASD-STE100-inspired)

| Rule | Detail |
|---|---|
| Length per point | **2–3 sentences. Never more than 3.** |
| Sentence length | 20 words or fewer |
| Voice | Active voice. Present tense where possible. |
| One idea per sentence | Do not join two ideas with "and" or a comma |
| Jargon | Define a term the first time it appears: "EPS, or earnings per share, is ..." |
| Consistent terms | Always the same word for the same thing: "revenue" (not "sales" / "top line"), "profit" or "net income" (not "bottom line"), "share" (not "stock unit") |
| Plain words | No idioms, metaphors, slang, or hype ("soared", "crushed it", "blowout") |
| Address | Speak about people in general ("Some investors look at ...") rather than telling the user what to do ("You should look at ...") |

**Good:** "Revenue is the money a company gets from selling its products. It is not the same as profit. Profit is what remains after costs."

**Bad:** "The company's top line soared thanks to blockbuster demand, which bodes well for shareholders going forward."

---

## 3. What the AI may use, and what it may never do

**Allowed inputs (only these):**
1. The facts in the request payload (numbers, directions, comparisons, dates computed by Python)
2. General financial definitions and background knowledge (what revenue is, how dividends work, what an ETF is)

**Forbidden, always:**

| # | Forbidden | Example of what NOT to write |
|---|---|---|
| F1 | Writing any number in earnings explanations | "Revenue grew 5%." (Python already shows the number) |
| F2 | Causal claims the data does not show | "Revenue rose because phone sales grew." |
| F3 | Claims about what any specific analyst, firm, or news source said or thinks | "Analysts at a big bank are bullish." |
| F4 | Recommendations: buy, sell, hold, invest, avoid | "This could be a good stock to buy." |
| F5 | Predictions about price, earnings, or dividends | "The dividend will likely grow." |
| F6 | Quality judgments about the company | "This is a strong company." / "The cash position is healthy." / "It has enough cash." |
| F7 | Value judgments: undervalued, overvalued, cheap, expensive, safe, risky (about this company) | "The stock looks cheap." |
| F8 | Facts about the company not in the payload | Product names, CEO, recent events, lawsuits |
| F9 | Words implying certainty: guaranteed, certain, always, never (about markets) | "Stocks always recover." |
| F10 | "Beat" / "missed" language | Use "above / below / equal to the analyst estimate" |

**When the data does not say why something changed**, the AI says so in plain words:
"The data does not show the reason for this change."

---

## 4. Profile framing

The profile changes the **framing and background**, never the conclusion. The AI never says the profile makes something right or wrong for the user.

| Profile | Framing allowed |
|---|---|
| Age 18–24, 25–34 | May mention that time horizon is one factor some people consider. Simplest definitions. |
| Age 35–49 | May mention balancing goals over different time periods |
| Age 50+ | May mention that some people focus more on stability and income as goals get closer |
| Risk: low | Background on how values can go down as well as up, and what diversification is |
| Risk: medium | Balanced background |
| Risk: high | Background on how higher possible returns usually come with bigger possible losses |

All framing stays general: "Some people with a longer time horizon ...". Never: "Because you are 22, you can take more risk."

---

## 5. Earnings explanations — `explain_earnings(facts, profile)`

### 5.1 What Claude receives

Python sends only the fields below. **No raw API responses. No news. No extra text.**

```json
{
  "is_etf": false,
  "profile": { "age_range": "25-34", "risk": "medium" },
  "headline": { "available": true, "comparison": "above" },
  "revenue":  { "available": true, "direction": "up" },
  "profit":   { "available": true, "direction": "down" },
  "eps":      { "available": true, "comparison": "above" },
  "cash":     { "available": true },
  "dividend": { "available": true, "pays_dividend": true }
}
```

Claude gets **directions and comparisons, not the numbers.** It cannot repeat or misread a number it never sees.
`available: false` means the value is `null`. For that section Claude returns `null`.
For `headline`, `available` is `false` when `comparison` is `null`. For `dividend`, `available` is `false` only when `pays_dividend` is `null` (unknown); a known non-payer (`false`) is available.

### 5.2 System prompt (put in `prompts.py` as `EARNINGS_SYSTEM_PROMPT`, word for word)

```
You are a patient teacher in a financial education app for beginners.
Your job is to explain what earnings data means in general terms, so people can think for themselves.

Rules you must follow:
- Write 2 or 3 short sentences for each item. Never more than 3.
- Each sentence has 20 words or fewer. Use active voice. One idea per sentence.
- Define financial terms the first time you use them.
- Never write any digits or numbers. The app shows all numbers separately.
- Never say why a value changed. You do not have that information. If useful, say: "The data does not show the reason for this change."
- Never mention a specific analyst, firm, news story, product, or person.
- Never recommend buying, selling, holding, or avoiding anything.
- Never predict the future.
- Never judge the company as strong, weak, healthy, safe, risky, cheap, or expensive.
- Do not use the words "beat" or "missed". Say "above", "below", or "equal to" the analyst estimate.
- Speak about people in general. Do not tell the reader what to do.
- If an item has "available": false, return null for that item.

Return only valid JSON with exactly these keys:
{"headline": string|null, "revenue": string|null, "profit": string|null, "eps": string|null,
 "cash": string|null, "dividend": string|null, "questions": [string, string, string]}

"questions" are 3 neutral questions a beginner could ask themselves when reading earnings.
Questions must not hint at an answer or a decision.
```

For ETFs, the same prompt is used with the keys replaced by:
`{"etf": string, "questions": [string, string, string]}`. The `etf` text explains what an ETF is and why it has no earnings report.

The user message is the JSON payload from 5.1 as a string.

### 5.3 Call settings

| Setting | Value |
|---|---|
| Model | `config.CLAUDE_MODEL` (`claude-sonnet-5-5`) |
| Max tokens | `config.AI_MAX_TOKENS_EARNINGS` |
| Timeout | `config.AI_TIMEOUT_SECONDS` |
| Cache | Key `ai:earnings:{ticker}:{period_end}:{age_range}:{risk}`, TTL `config.TTL_AI` |

### 5.4 Output validation (Python, after every Claude response)

Run these checks **per field**. A field that fails is replaced with its fallback sentence (section 7).

| Check | Rule |
|---|---|
| V1 JSON | Parse the first `{...}` block. If parsing fails → **all** fields use fallback, `explanation_source = "fallback"`. |
| V2 Keys | Missing key → that field uses fallback |
| V3 Digits | Field contains any digit `[0-9]` → fallback |
| V4 Banned terms | Field matches (case-insensitive, whole words via `\b...\b`) any of: `buy`, `sell`, `hold (it\|this\|the stock\|shares)`, `invest in`, `beat`, `missed`, `undervalued`, `overvalued`, `guarantee\w*`, `will rise`, `will fall`, `will grow`, `strong company`, `healthy`, `cheap`, `expensive`, `because` → fallback. Whole-word matching matters: "selling its products" and "ETFs hold many investments" must pass. |
| V5 Length | More than 3 sentences or any sentence over 30 words → fallback |
| V6 Null rule | If Python marked the section `available: false`, force `null` regardless of Claude's output |
| V7 Questions | ETF only: must be a list of exactly 3 strings, each ending in `?`, passing V3 and V4. Otherwise use the ETF fallback questions. Stock questions never come from Claude: they are always the fixed set for `profile.risk` in section 7. |

`explanation_source` is `"ai"` if at least one field came from Claude, otherwise `"fallback"`.
Log every replaced field at WARNING level with the check that failed, e.g. `[services.ai_service] V4 banned term in field=eps ticker=EXMPL`.

**Never raise from `explain_earnings`.** Any exception (timeout, network, API error) → full fallback.

> Note on V4: the banned list is strict on purpose. Fallback text is safe. A false positive costs nothing.

---

## 6. Chat — `chat(message, history, profile, context_facts)`

### 6.1 System prompt (put in `prompts.py` as `CHAT_SYSTEM_PROMPT`, word for word)

```
You are a patient teacher in a financial education app for beginners.
You explain financial ideas and the data shown in the app, so people can think for themselves.

Rules you must follow:
- Answer in 2 or 3 short sentences. Never more than 3 unless the user asks for more detail, and then at most 6.
- Each sentence has 20 words or fewer. Use active voice. One idea per sentence.
- Define financial terms the first time you use them.
- You may only use numbers that appear in the app data below. Copy them exactly. Never calculate new numbers.
- Never say why a company's numbers changed. The app data does not include reasons.
- Never mention what a specific analyst, firm, or news story said.
- Never recommend buying, selling, holding, or avoiding any investment.
- If someone asks whether to buy, sell, or hold, explain what factors people usually consider. Then say the pre-purchase checklist in the app can help them think it through.
- Never predict prices, earnings, or dividends.
- Never judge a company as good, bad, strong, weak, safe, risky, cheap, or expensive.
- If you do not know, or the app data does not include it, say so plainly.
- Speak about people in general. Do not tell the user what to do.

User profile (for framing only, never for advice): {profile}
App data currently on screen (may be empty): {context}
```

`{context}` is the snapshot and earnings `data` the browser sent, reduced to `display` strings,
labels, directions, and comparisons. Never include anything the browser did not send.

### 6.2 Call settings

| Setting | Value |
|---|---|
| Max tokens | `config.AI_MAX_TOKENS_CHAT` |
| History | Last `config.CHAT_HISTORY_LIMIT` messages only |
| Timeout | `config.AI_TIMEOUT_SECONDS`. On failure raise `AIUnavailable`. |
| Cache | None |

### 6.3 Chat validation (Python)

| Check | Rule |
|---|---|
| C1 Checklist link | `show_checklist_link = true` if the **user message** matches (case-insensitive) `\b(buy|sell|hold|invest in|should i|worth it|good investment)\b`. Decided by Python, not by Claude. |
| C2 Unverified numbers | Find every `$...` amount and `...%` value in the reply. If any does not appear exactly in the context `display` strings or the user's own message → replace the whole reply with: `"I can only use numbers that are shown in the app. Open a company on your watchlist, and I can explain its numbers."` Log at WARNING. |
| C3 Banned advice | If the reply contains `you should buy`, `you should sell`, `you should hold`, `guarantee`, `will rise`, `will fall` → replace with: `"I cannot give advice on what to buy or sell. I can explain how these ideas work. The pre-purchase checklist can help you think it through."` and set `show_checklist_link = true`. |

---

## 7. Fallback sentences (put in `prompts.py` as `FALLBACKS`, word for word)

Used when Claude fails or a field fails validation. Python picks the variant by `direction` / `comparison`.

**headline**
- above: "The company reported earnings per share above the analyst estimate. An analyst estimate is the average forecast from people who study the company. A result above it is often in the news, but it is only one piece of information."
- below: "The company reported earnings per share below the analyst estimate. An analyst estimate is the average forecast from people who study the company. A result below it is often in the news, but it is only one piece of information."
- equal: "The company reported earnings per share equal to the analyst estimate. An analyst estimate is the average forecast from people who study the company. This is only one piece of information."
- null comparison: no fallback. `headline` is null (V6).

**revenue**
- up: "Revenue is the money a company gets from selling its products or services. Revenue went up compared to the same quarter last year. The data does not show the reason for this change."
- down: "Revenue is the money a company gets from selling its products or services. Revenue went down compared to the same quarter last year. The data does not show the reason for this change."
- flat / null direction: "Revenue is the money a company gets from selling its products or services. It is not the same as profit. Comparing it to the same quarter last year shows the direction it moves."

**profit**
- up: "Profit, or net income, is the money left after the company pays its costs. Profit went up compared to the same quarter last year. Revenue and profit can move in different directions."
- down: "Profit, or net income, is the money left after the company pays its costs. Profit went down compared to the same quarter last year. Revenue and profit can move in different directions."
- flat / null direction: "Profit, or net income, is the money left after the company pays its costs. Revenue and profit can move in different directions. Looking at both gives a fuller picture."

**eps**
- any: "EPS, or earnings per share, is profit divided by the number of shares. It lets people compare profit across companies of different sizes. The analyst estimate is a forecast, not a promise."

**cash**
- any: "Cash and cash equivalents are money the company has or can get very quickly. Cash alone does not show if a company is doing well. Debts and costs also matter."

**dividend**
- pays: "A dividend is a payment a company makes to its shareholders. Companies choose if and when to pay dividends. A company can change or stop its dividend."
- does not pay: "This company did not pay a dividend in the data shown. Many companies keep their profit to grow the business instead. Not paying a dividend is common."
- unknown (`pays_dividend` null): no fallback. `dividend` is null (V6).

**etf**
- any: "An ETF, or exchange-traded fund, holds many investments in one fund. ETFs do not report earnings like a single company does. People often look at what the fund holds and what it costs."

**questions (stock), by profile risk.** Always used for stocks, also when Claude's explanations succeed. Python picks the set; Claude's `questions` are ignored. The debt and cash-flow questions are conceptual: the app shows no debt or cash-flow figures.

low:
1. "How consistently has the company generated profit and positive cash flow?"
2. "How much debt does the company have, and how could its debt obligations affect financial stability?"
3. "What financial risks would I want to understand before learning more about this company?"

medium:
1. "How have revenue, profit, and EPS changed compared with earlier periods?"
2. "Has the company's debt increased or decreased, and how does that compare with its cash generation?"
3. "What additional information would help me understand the balance between growth and financial risk?"

high:
1. "How quickly have revenue and earnings changed, and how consistent has that growth been?"
2. "How could borrowing and debt obligations affect the company if growth slows or business conditions change?"
3. "What could cause the company's financial results or share price to become more volatile?"

**questions (ETF)**
1. "What companies or assets does this fund hold?"
2. "What does this fund cost each year in fees?"
3. "How does this fund fit with what I already own?"

---

## 8. Required tests (Agent C, `tests/test_chat.py`, Claude always mocked)

| # | Test | Expected |
|---|---|---|
| T1 | Claude returns valid, clean JSON | All explanation fields from Claude, `explanation_source = "ai"`; stock questions are the fixed set for the profile risk |
| T2 | Claude returns non-JSON | All fields fallback, `"fallback"` |
| T3 | One field contains a digit | Only that field is fallback |
| T4 | One field contains "buy" | Only that field is fallback |
| T5 | Section has `available: false` but Claude wrote text | That field is `null` |
| T6 | Claude call raises timeout | Full fallback, no exception raised |
| T7 | ETF payload | Returns `etf` + 3 `questions` |
| T8 | Chat message "Should I buy EXMPL?" | `show_checklist_link = true` |
| T9 | Chat reply contains `$999.99` not in context | Reply replaced with the C2 message |
| T10 | Chat Claude call fails | Endpoint returns `ok: false`, code `AI_UNAVAILABLE` |
| T11 | Chat message empty or over 500 chars | `INVALID_REQUEST` |
| T15 | Facts with EPS `comparison: null`; Claude returns headline text | Payload has `headline.available: false`; `headline` is `null` |
| T16 | Known non-payer (`pays_dividend: false`), Claude call fails | Payload has `dividend.available: true`; `dividend` is the "does not pay" fallback. With `pays_dividend: null` and Claude text → `dividend` is `null` |
| T17 | Stock facts with each risk (`low`, `medium`, `high`); Claude returns its own questions | `questions` equals the section 7 set for that risk, for Claude success and fallback; still one Claude call; ETF questions unchanged |

---

## 9. Static copy deck (exact text for other agents)

All static user-facing text, in one place, written to the same style rules.

**Disclaimer footer** (B, `index.html`, always visible):
"This app is for education only. It does not give financial advice. Investing has risk, and you can lose money. Talk to a licensed professional before you make decisions."

**Earnings panel note** (B, under the earnings panel):
"Numbers come from company reports and data providers. Explanations are general education, not advice."

**Chat note** (C, under the chat input):
"The assistant explains ideas. It does not tell you what to buy or sell."

**Profile notes** (B, `profile.js`, shown on the snapshot by risk level):
- low: "You chose low risk. Some people with this preference focus on steady, diversified investments. Every investment can lose value."
- medium: "You chose medium risk. Some people with this preference balance growth and stability. Every investment can lose value."
- high: "You chose high risk. Higher possible returns usually come with bigger possible losses. Every investment can lose value."

**ETF message** (A, `earnings_service.py`, `etf_message` field):
"ETFs hold many companies. They do not report earnings. Look at the fund's holdings and fees instead."

**Demo badge** (B): `source: "demo"` → "Demo data (as of {as_of date})" · `"cache"` → "Saved data (as of {as_of time})" · `"live"` → "Live data"

**Simulated alert label** (D): "Simulated alert: demo only"

**Missing value** (everyone): "Data not available"

**Pre-purchase checklist** (D, `checklist.js`), title "Before you buy: questions to ask yourself":
1. Do I understand what this company or fund does?
2. Did I read its latest earnings results?
3. Do I have emergency savings first?
4. Can I accept losing some of this money?
5. Does this add to or reduce my diversification?
6. How long do I plan to hold it?
7. Did I check the fees (for ETFs)?
