# DEMO_SCRIPT.md — Presentation Runbook

> Owner: Planner. Put this in `docs/`. Practice the click path at least 3 times before 8:15 PM.
> Submission deadline: **8:45 PM PST**. Feature freeze: **7:30 PM**.

---

## 1. Presentation mode

**Present in demo mode.** Every number comes from real company data saved on Oct 24, 2026, and the badge on
each screen says "Demo data (as of Oct 24, 2026)". These are not live prices. Live mode (Finnhub + FMP) exists and
was tested separately, but its numbers differ from this script (for example, AAPL's EPS headline), so do not present it.

Rehearsals and the presentation use the same command. Run it from the project folder in PowerShell. Port 5000 must
be free: if another copy of the app is running, stop it first (Ctrl+C in its window).

```powershell
$env:DATA_MODE="demo"; $env:WARM_CACHE="0"; venv\Scripts\python app.py
```

- **Financial data:** demo mode reads only the saved data file. Finnhub and FMP are not called.
- **Claude:** the app uses the Anthropic key already in `.env`. Check `http://localhost:5000/api/health` after
  starting: `keys_present.anthropic` must be `true`.
- **Cost:** each earnings explanation that is not yet cached, and every chat message, is a paid Anthropic API call.
  Rehearsals and the pre-load clicks in §2 cost money too.
- **Loading time:** with `WARM_CACHE=0`, each company's first earnings load waits for Claude (a few seconds).
  Explanations are then kept for 24 hours while the server runs. See §2 for the pre-load clicks.

---

## 2. Before you present

### At 7:30 PM (feature freeze)
- [ ] All agents' commits are in. `git status` is clean.
- [ ] `pytest` passes.
- [ ] `git tag demo-ready` — this is your safe point. If anything breaks later: `git checkout demo-ready`.
- [ ] Record one full run of the click path (screen recording). This is your last-resort backup.

### 10 minutes before you present
- [ ] Laptop plugged in. Notifications off (Do Not Disturb).
- [ ] Start the command from §1. `/api/health` shows `anthropic: true`.
- [ ] **Pre-load the explanations:** in a normal window, onboard with 25–34 / Medium and click AAPL, KO and VOO once. Do not restart the server after this.
- [ ] Open a **private / incognito** window at `http://localhost:5000` so onboarding appears fresh.
- [ ] Browser zoom 125% so the room can read it.
- [ ] Close every other tab.
- [ ] **Do not onboard yet.** You do it live in step 2 below.

---

## 3. Click path (about 4 minutes)

Choose **25–34** and **Medium** in onboarding. That is the profile you pre-loaded, so the earnings clicks are instant.

| # | Do this | Say this (short) |
|---|---|---|
| 1 | Show the empty page with the onboarding modal | "Beginners get advice from social media and AI chats that sound sure of themselves. We built the opposite: an app that teaches, so people can think for themselves." |
| 2 | Pick 25–34, Medium. Save. | "Two questions. They change how things are explained, never what the app recommends. It does not recommend anything." |
| 3 | AAPL opens. Point at the badge and the snapshot. | "Every screen says where the data came from and when. This is real company data saved on October 24. The badge says demo data, so nobody mistakes it for live prices." |
| 4 | Scroll to earnings. Point at the headline. | "We say 'EPS vs. analyst estimate: Above', not 'beat'. We name the benchmark: the average analyst forecast. Words like 'beat' hide that." |
| 5 | Point at one number, then its explanation | "Key design rule: Python writes every number. For these explanations, Claude gets only facts like 'revenue went up', never the figures. It cannot misquote a number it never received." |
| 6 | Point at "Questions to think about" | "Instead of a conclusion, we give questions. The user does the thinking." |
| 7 | Click **KO**. Point at the dividend section. Open the bell. | "Alerts are simulated for the demo, and the app says so on every one. Their figures come from the same saved data." |
| 8 | Click **VOO** | "An ETF has no earnings report. Instead of showing empty boxes, the app teaches what an ETF is." |
| 9 | Chat: type **What is EPS?** | "Answers are short and in plain words, based on a writing standard from aerospace, ASD-STE100." |
| 10 | Chat: type **Should I buy Apple?** | "It will not tell you. It explains what people consider, and points to the checklist." |
| 11 | Click **Open the pre-purchase checklist** | "Seven questions to ask yourself. No score, no 'you are ready'. The decision stays with the person." |
| 12 | Close. Point at the footer. | "The disclaimer is always visible. Safety here is in the code, not only in a prompt: every AI answer is checked by Python before you see it." |

If a value shows **"Data not available"**, say: "When we don't have a number, we say so. We never estimate or fill gaps."

---

## 4. If something goes wrong on stage

| Problem | What to do |
|---|---|
| Page shows an error card | Click **Try again** once. If it repeats, move to the next ticker and keep talking. |
| Earnings text looks generic | That is the fallback text. It is correct and safe. Keep going. |
| Chat says the AI is unavailable | Say: "If the AI is down, the app tells you honestly instead of guessing." Open the checklist with **Before you buy** (step 11). |
| Whole app is broken | Stop the server (Ctrl+C). Run the §1 command again. Reload. Onboard again with 25–34 / Medium. |
| Laptop or server will not recover | Play the screen recording from 7:30 PM. |

---

## 5. Likely judge questions

| Question | Short answer |
|---|---|
| How do you stop the AI from making up numbers? | For earnings explanations, Claude never receives the numbers, only facts like "revenue went up". Python rejects any explanation that contains a digit. In chat, Claude sees only the figures already on screen, and Python replaces any reply with a dollar or percent figure that is not shown. |
| What stops it from giving advice? | Three layers: the prompt, a Python check for banned words like "buy" and "because", and safe pre-written fallback text. A false alarm only costs a plainer sentence. |
| Why not let the AI explain why revenue changed? | The data does not include the reason. Any reason would be a guess presented as fact. The app says "The data does not show the reason." |
| Where does the data come from? | Today: real data saved from Yahoo Finance on October 24, labeled with its date. The app also has a live mode with Finnhub for prices and earnings estimates and FMP for financial statements. We tested it separately. |
| Why "analyst estimate" and not "beat"? | "Beat" hides the benchmark. The estimate is the average analyst forecast, not the company's own target. We name it. |
| What about news? | We left it out on purpose. Many finance articles are auto-generated to push a story. We did not want to feed that into explanations. |
| What happens when an API fails? | Each provider failure falls back to saved real data, labeled as such. One missing field shows "Data not available". It never crashes or guesses. |
| Why the short sentences? | ASD-STE100 is a controlled-English standard for clear technical writing. Python rejects any earnings explanation longer than three sentences. Chat is asked to stay short. |
| What would you build next? | A custom data pipeline to replace the saved-data script, more tickers, and lessons that link from each explanation. |
