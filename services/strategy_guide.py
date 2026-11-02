"""Test a strategy explanations (P5 step 8): the owner-approved text in data/strategy_guide.json, copied word for word
from docs/P5_CONTENT.md, and each card's reading filled in from a run's own results (the /api/backtest/run reply).
Nothing is recalculated: every number is one the engine already returned, only formatted. Static text: no AI, no
network."""
import json
import os
from datetime import date

GUIDE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "strategy_guide.json")
MINUS = "−"
RULE_PARTS = ("title", "setup", "what", "why", "watch", "start", "readings.acted", "readings.none")
METRIC_PARTS = {"total_return": ("reading", "what", "watch"),
                "difference": ("reading", "level", "what", "how", "watch"),
                "drawdown": ("readings.fell", "readings.never", "readings.cash", "what", "watch"),
                "volatility": ("reading", "what", "watch"), "trades": ("reading", "what", "watch"),
                "days_invested": ("reading", "what", "watch"),
                "costs": ("readings.example", "readings.none", "what", "watch")}
REQUIRED = (["label", "footer", "not_a_forecast.title", "not_a_forecast.text", "slippage.title", "slippage.what",
             "slippage.watch", "halves.title", "halves.how", "buy_hold.title", "buy_hold.what", "buy_hold.why",
             "buy_hold.watch", "buy_hold.readings.bought", "buy_hold.readings.skipped"]
            + [f"rules.{r}.{p}" for r in ("sma_cross", "rsi_threshold") for p in RULE_PARTS]
            + [f"metrics.{m}.title" for m in METRIC_PARTS]
            + [f"metrics.{m}.{p}" for m, parts in METRIC_PARTS.items() for p in parts])
_guide = None


def load(path=GUIDE_PATH):
    """The guide, refused unless every text the cards use is present and non-empty."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for dotted in REQUIRED:
        node = data
        for key in dotted.split("."):
            node = node.get(key) if isinstance(node, dict) else None
        if not isinstance(node, str) or not node.strip():
            raise ValueError(f"The strategy guide is missing {dotted}.")
    return data


def guide():
    global _guide
    if _guide is None:
        _guide = load()
    return _guide


def fill(template, **values):
    for key, value in values.items():
        template = template.replace("{" + key.replace("_", " ") + "}", str(value)).replace("{" + key + "}", str(value))
    return template


def money(cents):  # the "$" is in the approved templates
    return (MINUS if cents < 0 else "") + f"{abs(cents) // 100:,}.{abs(cents) % 100:02d}"


def pct(value, signed=False):  # the API's two-decimal percentage, as the results table shows it
    return (MINUS if value < 0 else "+" if signed and value > 0 else "") + f"{abs(value):.2f}%"


def short_date(iso):
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


def times(n):
    return "once" if n == 1 else f"{n} times"


def readings(data):
    """One sentence per card from a /api/backtest/run reply with a result: the rule, buy and hold and each metric."""
    g, r = guide(), data["result"]
    s, b = r["strategy"], r["benchmark"]
    sm, bm = s["metrics"], b["metrics"]
    out = {}

    # the rule: the buy and sell decisions it acted on (fills, skipped entries and a decision on the last day)
    unacted = (r["unacted_signal"] or {}).get("side")
    buys = sum(f["side"] == "buy" for f in s["fills"]) + len(s["skipped"]) + (unacted == "buy")
    sells = sum(f["side"] == "sell" for f in s["fills"]) + (unacted == "sell")
    rule = g["rules"][data["preset"]]["readings"]
    if buys + sells == 0:
        out["rule"] = rule["none"]
    else:
        text = fill(rule["acted"], n=buys + sells, up=buys, down=sells, low=buys, high=sells)
        out["rule"] = text.replace(" 1 crossings:", " 1 crossing:").replace(" 1 RSI readings:", " 1 RSI reading:")

    bh = g["buy_hold"]["readings"]
    if b["fills"]:
        f = b["fills"][0]
        out["buy_hold"] = fill(bh["bought"], shares=f["shares"], open=money(f["open_cents"]),
                               price=money(f["price_cents"])).replace(" bought 1 shares ", " bought 1 share ")
    else:
        out["buy_hold"] = fill(bh["skipped"], price=money(b["skipped"][0]["price_cents"]))

    m = g["metrics"]
    out["total_return"] = fill(m["total_return"]["reading"], end=money(sm["final_value_cents"]),
                               **{"return": pct(sm["total_return_pct"], True)})
    diff = r["difference_pp"]
    sentence = fill(m["difference"]["reading"], end=money(sm["final_value_cents"]), symbol=data["symbol"],
                    bh_end=money(bm["final_value_cents"]), bh_return=pct(bm["total_return_pct"], True),
                    points=f"{abs(diff):.2f}", **{"return": pct(sm["total_return_pct"], True),
                                                  "higher | lower": "higher" if diff > 0 else "lower"})
    if diff == 0:
        sentence = sentence[:sentence.index(", so the rule ended")] + m["difference"]["level"]
    out["difference"] = sentence

    dd = m["drawdown"]["readings"]
    if sm["max_drawdown"]:
        out["drawdown"] = fill(dd["fell"], pct=pct(sm["max_drawdown_pct"]),
                               peak_date=short_date(sm["max_drawdown"]["peak"]["date"]),
                               trough_date=short_date(sm["max_drawdown"]["trough"]["date"]))
    else:
        out["drawdown"] = dd["cash"] if sm["days_invested"] == 0 else dd["never"]
    out["volatility"] = fill(m["volatility"]["reading"], vol=pct(sm["daily_volatility_pct"]))
    out["trades"] = (m["trades"]["reading"].replace("{buys} times", times(sm["buys"]))
                     .replace("{sells} times", times(sm["sells"])))
    out["days_invested"] = fill(m["days_invested"]["reading"], n=sm["days_invested"], days=sm["evaluation_days"],
                                pct=pct(sm["days_invested_pct"]))
    costs = m["costs"]["readings"]
    fills = len(s["fills"])
    out["costs"] = costs["none"] if data["costs"] == "none" else fill(
        costs["example"], costs=money(sm["costs_paid_cents"]), fills=fills).replace(" 1 fills.", " 1 fill.")
    return out
