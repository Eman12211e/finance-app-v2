# API_CONTRACT.md — Financial Education MVP

> Every field name, type, and nesting level here is fixed. Backend and frontend agents
> build against this file in parallel. If you need a change, report it. Do not improvise.

**All example values in this file are fake.** The ticker `EXMPL` and every number in the
examples are placeholders. Never copy example numbers into code or data.

---

## 1. Standard response envelope

Every `/api/*` endpoint returns this shape. No exceptions.

**Success** (HTTP 200)
```json
{
  "ok": true,
  "data": { },
  "source": "live",
  "as_of": "2026-10-24T19:30:00Z",
  "error": null
}
```

**Failure** (HTTP status from the error table)
```json
{
  "ok": false,
  "data": null,
  "source": null,
  "as_of": null,
  "error": { "code": "DATA_NOT_AVAILABLE", "message": "No data is available for EXMPL." }
}
```

| Field | Type | Rule |
|---|---|---|
| `ok` | bool | `true` only if `data` is real and complete for the request |
| `data` | object \| null | Endpoint-specific, see below |
| `source` | `"live"` \| `"cache"` \| `"demo"` \| null | Where the financial data came from. `"cache"` is used **only** for a memoized live result; memoized demo data stays `"demo"` (ARCHITECTURE §4 provenance rule). Chat uses the source of its context, or `null` if no ticker context. |
| `as_of` | ISO 8601 UTC string \| null | `live`: fetch time. `cache`: original fetch time. `demo`: `generated_at` from `demo_stocks.json`. |
| `error` | object \| null | `{code, message}`. `message` is plain language, safe to show users, never contains keys or stack traces. |

### Error codes

| Code | HTTP | When |
|---|---|---|
| `INVALID_TICKER` | 400 | Ticker fails `^[A-Z]{1,5}(\.[A-Z])?$` after uppercasing |
| `INVALID_PROFILE` | 400 | `age_range` or `risk` not in allowed lists |
| `INVALID_REQUEST` | 400 | Missing or malformed body field (e.g. empty chat message, message over 500 chars) |
| `DATA_NOT_AVAILABLE` | 404 | Live failed (or demo mode) AND ticker not in demo data |
| `PROVIDER_ERROR` | 502 | Reserved for logging. Routes should fall back to demo instead of returning this when possible. |
| `AI_UNAVAILABLE` | 503 | Chat only. Claude call failed or timed out. (Earnings never returns this; it uses fallback text.) |
| `INTERNAL_ERROR` | 500 | Anything unexpected. Full traceback goes to the server log only. |

---

## 2. Display formatting rules

Python sends both the raw number and a ready-to-show string. The frontend shows `display`
and never formats financial numbers itself. Formatting lives in `services/formatting.py` (Agent A).

| Kind | Rule | Example (fake) |
|---|---|---|
| Large money | ≥ 1e12 → `T`, ≥ 1e9 → `B`, ≥ 1e6 → `M`, 2 decimals | `$12.34B` |
| Per-share money | 2 decimals | `$1.23` |
| Percent change | 1 decimal, always signed | `+4.5%`, `-2.0%` |
| Percent level | 2 decimals, no sign | `0.03%` |
| Date | `Mon D, YYYY` | `Jun 27, 2026` |
| Missing | the exact string `"Data not available"` | — |

Raw money values are plain numbers in full currency units (dollars, not millions).

---

## 3. Endpoints

### 3.1 `GET /api/health` (owner: W0, defined in `app.py`)

For debugging. Never exposes key values.

```json
{ "ok": true, "source": null, "as_of": null, "error": null,
  "data": { "status": "ok", "data_mode": "demo",
            "keys_present": { "anthropic": true, "finnhub": true, "fmp": false } } }
```

---

### 3.2 `GET /api/stocks/<ticker>/snapshot` (owner: A)

No query params. No AI. Profile note is added by the frontend, not here.

**`data`:**
```json
{
  "ticker": "EXMPL",
  "name": "Example Corp",
  "is_etf": false,
  "exchange": "NASDAQ",
  "currency": "USD",
  "sector": "Technology",
  "description": "Example Corp makes widgets. It sells them in many countries.",
  "price":          { "value": 123.45, "display": "$123.45" },
  "change_percent": { "value": 1.2,    "display": "+1.2%" },
  "market_cap":     { "value": 1.5e12, "display": "$1.50T" },
  "dividend_yield": { "value": 0.5,    "display": "0.50%" },
  "expense_ratio":  { "value": null,   "display": "Data not available" }
}
```

| Field | Rule |
|---|---|
| `description` | First 2 sentences of the provider's business description. Truncate by sentence, never mid-sentence. `null` if missing. |
| `dividend_yield` | Percent level. `null` value if the company pays no dividend or data is missing. |
| `expense_ratio` | ETFs only. For stocks, always `{ "value": null, "display": "Data not available" }`. |
| Any `{value, display}` | If `value` is `null`, `display` is `"Data not available"`. |
| Plain-string fields (`name`, `exchange`, `currency`, `sector`) | May be `null` in live mode (providers often return no profile for ETFs). UI: a null `name` shows the ticker instead; the others show "Data not available". |

---

### 3.3 `GET /api/stocks/<ticker>/earnings?age_range=25-34&risk=medium` (owner: A, calls C's `explain_earnings`)

Both query params required and validated. Python builds every number; `explain` fields
come from `ai_service.explain_earnings()`.

**`data` for a stock:**
```json
{
  "ticker": "EXMPL",
  "is_etf": false,
  "etf_message": null,
  "period": {
    "label": "Quarter ended Jun 27, 2026",
    "period_end": "2026-06-27"
  },
  "headline": {
    "comparison": "above",
    "label": "EPS vs. analyst estimate: Above",
    "explain": "..."
  },
  "sections": {
    "revenue": {
      "title": "Revenue",
      "value":             { "value": 1.0e10, "display": "$10.00B" },
      "prior_year_value":  { "value": 9.5e9,  "display": "$9.50B" },
      "change_percent":    { "value": 5.3,    "display": "+5.3%" },
      "direction": "up",
      "explain": "..."
    },
    "profit": {
      "title": "Profit (net income)",
      "value":             { "value": 2.0e9,  "display": "$2.00B" },
      "prior_year_value":  { "value": 1.8e9,  "display": "$1.80B" },
      "change_percent":    { "value": 11.1,   "display": "+11.1%" },
      "direction": "up",
      "explain": "..."
    },
    "eps": {
      "title": "Earnings per share vs. analyst estimate",
      "period_label": "Quarter ended Jun 27, 2026",
      "report_date": "2026-07-30",
      "actual":     { "value": 1.23, "display": "$1.23" },
      "estimate":   { "value": 1.20, "display": "$1.20" },
      "difference": { "value": 0.03, "display": "$0.03" },
      "comparison": "above",
      "source_label": "Analyst average estimate (source: Finnhub)",
      "explain": "..."
    },
    "cash": {
      "title": "Cash and cash equivalents",
      "value": { "value": 3.0e10, "display": "$30.00B" },
      "explain": "..."
    },
    "dividend": {
      "title": "Dividend",
      "pays_dividend": true,
      "last_amount":  { "value": 0.25, "display": "$0.25" },
      "last_ex_date": "2026-08-10",
      "explain": "..."
    }
  },
  "questions_to_think_about": [ "...", "...", "..." ],
  "explanation_source": "ai"
}
```

**`data` for an ETF (`is_etf: true`):**
```json
{
  "ticker": "EXMPL",
  "is_etf": true,
  "etf_message": "ETFs hold many companies. They do not report earnings. Look at the fund's holdings and fees instead.",
  "etf_explain": "...",
  "period": null,
  "headline": null,
  "sections": null,
  "questions_to_think_about": [ "...", "...", "..." ],
  "explanation_source": "ai"
}
```

#### Computation rules (Python, `earnings_service.build_facts`)

| Item | Rule |
|---|---|
| Current quarter | `quarters[0]` (newest) from financials |
| Prior year value | The quarter whose `period_end` is 350–380 days before the current one. If none exists → `null`. **Never** substitute a different quarter. |
| `change_percent` | `(current - prior) / abs(prior) * 100`. `null` if either is `null` or prior is `0`. |
| `direction` | `"up"` if change > +0.5, `"down"` if < -0.5, `"flat"` otherwise, `null` if change is `null` |
| EPS `difference` | `actual - estimate`, rounded to 2 decimals. `null` if either missing. |
| EPS `comparison` | `"above"` if difference ≥ 0.01, `"below"` if ≤ -0.01, `"equal"` otherwise, `null` if difference is `null` |
| `headline.comparison` | Same as EPS `comparison` |
| `headline.label` | `"EPS vs. analyst estimate: Above"` / `"Below"` / `"Equal"`. If `null` → `"EPS vs. analyst estimate: Data not available"` |
| EPS source rule | `actual` and `estimate` must come from the **same** record of the **same** provider. Never mix providers. |
| `source_label` | `"Analyst average estimate (source: Finnhub)"` for live; `"Analyst average estimate (source: demo data)"` for demo |
| Dividend | `pays_dividend: false` → `last_amount` is `{null, "Data not available"}`, `last_ex_date` null. Unknown → `pays_dividend: null`. |

#### Explanation rules (from `explain_earnings`)

- Keys returned for stocks: `headline`, `revenue`, `profit`, `eps`, `cash`, `dividend`, `questions` (list of 3).
  For ETFs: `etf`, `questions`.
- Mapping into `data`: `headline` → `headline.explain`; each section key → `sections.<key>.explain`;
  `questions` → `questions_to_think_about`; `etf` → `etf_explain`. Stock responses have no `etf_explain` field.
- For stocks, `questions_to_think_about` is always the fixed 3-question set for the request's `risk` (AI_RULES §7), never Claude's. ETFs keep their current questions.
- If the section's main value is `null`, its `explain` is `null`. For `headline`, the main value is `comparison`. For `dividend`, the main value is `pays_dividend`: `true` or `false` gets an explanation, `null` (unknown) gets `null`. The UI then shows nothing extra.
- `explanation_source`: `"ai"` if Claude's output was used, `"fallback"` if pre-written text was used.
- Full content rules: `docs/AI_RULES.md`.

---

### 3.4 `POST /api/chat` (owner: C)

**Request body:**
```json
{
  "message": "What does EPS mean?",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ],
  "profile": { "age_range": "25-34", "risk": "medium" },
  "context": {
    "ticker": "EXMPL",
    "source": "demo",
    "as_of": "2026-10-24T20:00:00Z",
    "snapshot": { },
    "earnings": { }
  }
}
```

| Field | Rule |
|---|---|
| `message` | Required, 1–500 chars after trim |
| `history` | Optional. Server keeps only the last `CHAT_HISTORY_LIMIT` (6) items. Roles only `user` / `assistant`. |
| `profile` | Required, validated |
| `context` | Optional, may be `null`. `snapshot` and `earnings` are the `data` objects the browser already received. Server passes only numbers/text from these to Claude; never fetches extra data for chat. |

**`data`:**
```json
{
  "reply": "EPS means earnings per share. It is the profit divided by the number of shares. ...",
  "show_checklist_link": false
}
```

`show_checklist_link` is `true` when the user asks whether to buy, sell, or hold. The frontend
then shows a "Open the pre-purchase checklist" link under the reply.

`source` / `as_of`: copied from `context.source` / `context.as_of`, if context was sent; otherwise `null`.

---

### 3.5 `GET /api/alerts?tickers=AAPL,KO` (owner: D)

`tickers` required, comma-separated, each validated. Unknown tickers are skipped, not errors.
`source` is always `"demo"`.

**`data`:**
```json
{
  "alerts": [
    {
      "id": "EXMPL-dividend-2026-08-10",
      "ticker": "EXMPL",
      "type": "dividend",
      "title": "Dividend paid",
      "body": "Example Corp paid a dividend of $0.25 per share. The ex-dividend date was Aug 10, 2026.",
      "event_date": "2026-08-10",
      "simulated": true,
      "label": "Simulated alert: demo only"
    }
  ]
}
```

| Rule |
|---|
| `type` is `"dividend"` or `"earnings"` |
| Every figure and date in `body` comes from `demo_stocks.json`. Nothing hand-written. |
| An earnings alert uses `next_earnings_date` and must say "expected": `"Example Corp is expected to report earnings on Oct 30, 2026."` |
| If the needed value is `null`, that alert is not created. |
| `simulated` is always `true`. `label` is always exactly `"Simulated alert: demo only"`. |
| Sort newest `event_date` first. |

---

### 3.6 Optional Sentiment Explorer (owner: Integrator)

Off unless `SENTIMENT_ENABLED=1`. Classifies fixed, fictional example statements from `data/sentiment_statements.json`
with the local `ProsusAI/finbert` model. No AI (Claude), no market data, no free-text input. `source` and `as_of` are always `null`.

`GET /api/sentiment/statements` → `data`:
```json
{ "enabled": false, "model": "ProsusAI/finbert",
  "note": "These example statements are fictional and written for this app. ...",
  "statements": [ { "id": "outlook-raised", "text": "The company raised its full-year sales outlook after a strong quarter." } ] }
```

`POST /api/sentiment` with body `{ "statement_id": "outlook-raised" }` → `data`:
```json
{ "statement_id": "outlook-raised", "text": "...", "model": "ProsusAI/finbert",
  "inference": "model", "label": "positive",
  "scores": { "positive": { "value": 94.12, "display": "94.12%" },
              "negative": { "value": 2.10,  "display": "2.10%" },
              "neutral":  { "value": 3.78,  "display": "3.78%" } },
  "reason": null }
```

| Rule |
|---|
| `inference` is `"model"` only when FinBERT actually ran. `label` is the highest of the model's three scores; it is never chosen or invented by the app. |
| Disabled, packages missing, weights missing, load failure, inference failure or unexpected labels → `inference: "unavailable"`, `label: null`, `scores: null`, and a plain-language `reason`. HTTP 200, `ok: true`. |
| Unknown, empty or missing `statement_id` → `INVALID_REQUEST` (400). |
| The model loads lazily from the local Hugging Face cache (`local_files_only`); a request never downloads weights. Real model results are cached per statement for the process. |

## 4. `data/demo_stocks.json` schema

This is the contract between the data generator and the app. Any generator (yfinance today,
a custom pipeline later) must write exactly this shape.

```json
{
  "generated_at": "2026-10-24T20:00:00Z",
  "generator": "yfinance",
  "tickers": {
    "EXMPL": {
      "snapshot": {
        "ticker": "EXMPL",
        "name": "Example Corp",
        "is_etf": false,
        "exchange": "NASDAQ",
        "currency": "USD",
        "sector": "Technology",
        "description_full": "Full business description text...",
        "price": 123.45,
        "change_percent": 1.2,
        "market_cap": 1.5e12,
        "dividend_yield": 0.5,
        "expense_ratio": null
      },
      "financials": {
        "quarters": [
          { "period_end": "2026-06-27", "revenue": 1.0e10, "net_income": 2.0e9, "cash_and_equivalents": 3.0e10 },
          { "period_end": "2026-03-28", "revenue": null,   "net_income": null,  "cash_and_equivalents": null }
        ],
        "eps": {
          "period_end": "2026-06-27",
          "report_date": "2026-07-30",
          "actual": 1.23,
          "estimate": 1.20
        },
        "dividend": {
          "pays_dividend": true,
          "last_amount": 0.25,
          "last_ex_date": "2026-08-10"
        },
        "next_earnings_date": "2026-10-30"
      }
    }
  }
}
```

| Rule |
|---|
| Snapshot values here are raw numbers. `market_data` converts them to `{value, display}` for the API. |
| `quarters`: newest first, up to 5 entries (5 are needed to find the same quarter last year). |
| Any value the generator cannot get is `null`. The generator never estimates or fills gaps. |
| ETFs: `financials.quarters` is `[]`, `eps` is `null`. `dividend` and `expense_ratio` may be filled. |
| `eps.actual` and `eps.estimate` come from the same provider record. |
| `dividend_yield` and `expense_ratio` are percent levels (e.g. `0.5` means 0.5%). The generator converts if the provider uses fractions. |

### Live data mapping

When `DATA_MODE=live`, `market_data` must return the **same internal shape** as the
`snapshot` and `financials` objects above, whatever provider it uses. That way
`earnings_service.build_facts()` never knows where data came from.

| Internal field | Live provider (Agent A/E confirm with `check_endpoints.py`) |
|---|---|
| price, change_percent | Finnhub `/quote` |
| name, exchange, sector, market_cap | Finnhub `/stock/profile2` |
| description_full | FMP profile |
| quarters (revenue, net_income) | FMP quarterly income statement |
| quarters (cash_and_equivalents) | FMP quarterly balance sheet |
| eps (actual, estimate, period_end) | Finnhub `/stock/earnings` (same record) |
| dividend | FMP (endpoint confirmed by check script) |
| next_earnings_date | Finnhub `/calendar/earnings` |
| dividend_yield | Finnhub `/stock/metric?metric=all` → `dividendYieldIndicatedAnnual` (Agent E verifies on the free tier; if not available → `null`) |
| expense_ratio | No free live source. **Always `null` in live mode.** Shown as "Data not available". |

If `check_endpoints.py` shows an endpoint FAILs on the free tier, that field comes from
demo data and is tagged as such in logs. Never call a failing endpoint at runtime.

---

## 5. localStorage keys (browser, owner: B unless noted)

| Key | Shape |
|---|---|
| `fe_profile` | `{ "age_range": "25-34", "risk": "medium" }` |
| `fe_watchlist` | `["AAPL", "MSFT", "KO", "NVDA", "VOO"]` (default on first load) |
| `fe_alerts_read` (owner: D) | `["AAPL-dividend-2026-08-10", ...]` ids of alerts already seen |

Wrap every read/write in `try/catch`. If storage fails, the app still works with defaults for that session.

---

## 6. Frontend module contract (browser)

No frameworks, no ES module bundling. Each JS file attaches one object to `window` and
talks to other modules **only** through these objects and the events below.

### Script order in `index.html` (owner: B)
`api.js` → `profile.js` → `watchlist.js` → `company.js` → `chat.js` → `alerts.js` → `checklist.js` → `risk_education.js` → `accounts.js` → `sentiment.js` → `app.js`

All are loaded with `defer`. A missing file (before its agent builds it) must not break the page.
`app.js` checks `if (window.Chat) window.Chat.init()` etc. before calling.

### Globals

| Global | Owner | Must expose |
|---|---|---|
| `window.Api` | B | `getSnapshot(ticker)`, `getEarnings(ticker, profile)`, `postChat(body)`, `getAlerts(tickers)`, `getHealth()` — each returns a Promise of the **envelope**. Network failure resolves (never rejects) to `{ok:false, data:null, source:null, as_of:null, error:{code:"NETWORK_ERROR", message:"Could not reach the server."}}` |
| `window.Profile` | B | `init()`, `get()` → profile object or `null`, `open()` opens the modal |
| `window.Watchlist` | B | `init()`, `get()` → array of tickers |
| `window.Company` | B | `init()`, `getCurrent()` → `{ticker, source, as_of, snapshot, earnings}` or `null` |
| `window.Chat` | C | `init()` |
| `window.Alerts` | D | `init()` |
| `window.Checklist` | D | `init()`, `open()` |
| `window.RiskEducation` | Integrator | `init()`. Static panel, no network calls; re-renders on `app:profile-changed` |
| `window.Accounts` | Integrator | `init()`, `open()`. Static "Brokerage & Investing Accounts 101" modal, no network calls |
| `window.Sentiment` | Integrator | `init()`, `open()`. Optional Sentiment Explorer; shows its header button only when `/api/sentiment/statements` reports `enabled: true`. `window.Api` also exposes `getSentimentStatements()` and `postSentiment(statementId)`. |

### DOM containers (created by B in `index.html`)

| id | Filled by |
|---|---|
| `#profile-chip` | B |
| `#watchlist-root` | B |
| `#snapshot-root` | B |
| `#earnings-root` | B |
| `#chat-root` | C |
| `#alerts-root` (in the header) | D |
| `#checklist-root` (modal container) | D |
| `#risk-education` (bottom of the watchlist sidebar) | Integrator (`risk_education.js`) |
| `#accounts-open` (header button "Learn about accounts") | B creates it; `accounts.js` opens the modal on click |
| `#accounts-root` (modal container) | Integrator (`accounts.js`) |
| `#sentiment-open` (header button "Sentiment Explorer", `hidden` by default) | B creates it; `sentiment.js` shows it when enabled |
| `#sentiment-root` (modal container) | Integrator (`sentiment.js`) |
| `#checklist-open` (header button, created by B) | B creates it; click dispatches `app:open-checklist` |
| `#disclaimer-footer` | B |

### Events (all on `document`, `CustomEvent`, data in `detail`)

| Event | Fired by | `detail` | Listeners |
|---|---|---|---|
| `app:profile-changed` | Profile | `{profile}` | Company (reloads earnings), Chat, RiskEducation |
| `app:watchlist-changed` | Watchlist | `{tickers}` | Alerts |
| `app:ticker-selected` | Watchlist | `{ticker}` | Company |
| `app:company-loaded` | Company | `{ticker, source, as_of, snapshot, earnings}` (earnings may be `null` until loaded; fired again when earnings arrive) | Chat |
| `app:open-checklist` | header button, Chat | `{}` | Checklist |

### Safety rule for all frontend code
Insert any text from the server or the user with `textContent`, never `innerHTML`.
