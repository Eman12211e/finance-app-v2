# Owner: Agent C. All prompt text and fallback sentences, word for word from docs/AI_RULES.md.
import re

_STOCK_KEYS_INSTRUCTION = """Return only valid JSON with exactly these keys:
{"headline": string|null, "revenue": string|null, "profit": string|null, "eps": string|null,
 "cash": string|null, "dividend": string|null, "questions": [string, string, string]}"""

EARNINGS_SYSTEM_PROMPT = """You are a patient teacher in a financial education app for beginners.
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

""" + _STOCK_KEYS_INSTRUCTION + """

"questions" are 3 neutral questions a beginner could ask themselves when reading earnings.
Questions must not hint at an answer or a decision."""

ETF_KEYS_INSTRUCTION = """Return only valid JSON with exactly these keys:
{"etf": string, "questions": [string, string, string]}
The "etf" text explains what an ETF is and why it has no earnings report."""

ETF_SYSTEM_PROMPT = EARNINGS_SYSTEM_PROMPT.replace(_STOCK_KEYS_INSTRUCTION, ETF_KEYS_INSTRUCTION)
assert ETF_SYSTEM_PROMPT != EARNINGS_SYSTEM_PROMPT

CHAT_SYSTEM_PROMPT = """You are a patient teacher in a financial education app for beginners.
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
App data currently on screen (may be empty): {context}"""

FALLBACKS = {
    "headline": {
        "above": "The company reported earnings per share above the analyst estimate. An analyst estimate is the average forecast from people who study the company. A result above it is often in the news, but it is only one piece of information.",
        "below": "The company reported earnings per share below the analyst estimate. An analyst estimate is the average forecast from people who study the company. A result below it is often in the news, but it is only one piece of information.",
        "equal": "The company reported earnings per share equal to the analyst estimate. An analyst estimate is the average forecast from people who study the company. This is only one piece of information.",
    },
    "revenue": {
        "up": "Revenue is the money a company gets from selling its products or services. Revenue went up compared to the same quarter last year. The data does not show the reason for this change.",
        "down": "Revenue is the money a company gets from selling its products or services. Revenue went down compared to the same quarter last year. The data does not show the reason for this change.",
        "flat": "Revenue is the money a company gets from selling its products or services. It is not the same as profit. Comparing it to the same quarter last year shows the direction it moves.",
    },
    "profit": {
        "up": "Profit, or net income, is the money left after the company pays its costs. Profit went up compared to the same quarter last year. Revenue and profit can move in different directions.",
        "down": "Profit, or net income, is the money left after the company pays its costs. Profit went down compared to the same quarter last year. Revenue and profit can move in different directions.",
        "flat": "Profit, or net income, is the money left after the company pays its costs. Revenue and profit can move in different directions. Looking at both gives a fuller picture.",
    },
    "eps": {
        "any": "EPS, or earnings per share, is profit divided by the number of shares. It lets people compare profit across companies of different sizes. The analyst estimate is a forecast, not a promise.",
    },
    "cash": {
        "any": "Cash and cash equivalents are money the company has or can get very quickly. Cash alone does not show if a company is doing well. Debts and costs also matter.",
    },
    "dividend": {
        "pays": "A dividend is a payment a company makes to its shareholders. Companies choose if and when to pay dividends. A company can change or stop its dividend.",
        "does_not_pay": "This company did not pay a dividend in the data shown. Many companies keep their profit to grow the business instead. Not paying a dividend is common.",
    },
    "etf": {
        "any": "An ETF, or exchange-traded fund, holds many investments in one fund. ETFs do not report earnings like a single company does. People often look at what the fund holds and what it costs.",
    },
    "questions": {
        "etf": [
            "What companies or assets does this fund hold?",
            "What does this fund cost each year in fees?",
            "How does this fund fit with what I already own?",
        ],
    },
}

# Stock "Questions to think about": always this fixed set for profile.risk, never Claude's (AI_RULES §7).
STOCK_QUESTIONS = {
    "low": [
        "How consistently has the company generated profit and positive cash flow?",
        "How much debt does the company have, and how could its debt obligations affect financial stability?",
        "What financial risks would I want to understand before learning more about this company?",
    ],
    "medium": [
        "How have revenue, profit, and EPS changed compared with earlier periods?",
        "Has the company's debt increased or decreased, and how does that compare with its cash generation?",
        "What additional information would help me understand the balance between growth and financial risk?",
    ],
    "high": [
        "How quickly have revenue and earnings changed, and how consistent has that growth been?",
        "How could borrowing and debt obligations affect the company if growth slows or business conditions change?",
        "What could cause the company's financial results or share price to become more volatile?",
    ],
}

CHAT_FALLBACK_NUMBERS = "I can only use numbers that are shown in the app. Open a company on your watchlist, and I can explain its numbers."
CHAT_FALLBACK_ADVICE = "I cannot give advice on what to buy or sell. I can explain how these ideas work. The pre-purchase checklist can help you think it through."

# V4: whole-word matching, so "selling its products" and "ETFs hold many investments" pass
BANNED_EARNINGS_PATTERNS = re.compile(
    r"\b(buy|sell|hold (it|this|the stock|shares)|invest in|beat|missed|undervalued|overvalued|guarantee\w*"
    r"|will rise|will fall|will grow|strong company|healthy|cheap|expensive|because)\b",
    re.IGNORECASE,
)
# C3
BANNED_CHAT_PATTERNS = re.compile(
    r"\b(you should buy|you should sell|you should hold|guarantee\w*|will rise|will fall)\b", re.IGNORECASE
)
# C1
CHECKLIST_TRIGGER = re.compile(r"\b(buy|sell|hold|invest in|should i|worth it|good investment)\b", re.IGNORECASE)
