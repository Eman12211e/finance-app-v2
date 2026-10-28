"""P4 final QA (step 8): the indicator maths checked against a separate, deliberately naive reference written here,
for every symbol of both markets and through the analysis API; and the optional browser QA scripts stay optional,
local-only and zero-cost."""
import os
import re

import pytest

from services import indicators as ind
from services import paper_engine as eng
from services import paper_market

ROOT = os.path.join(os.path.dirname(__file__), "..")


# ---- an independent reference (plain loops, textbook definitions) ----

def ref_sma(xs, n):
    return [sum(xs[i - n + 1:i + 1]) / n if i >= n - 1 else None for i in range(len(xs))]


def ref_ema(xs, n):
    out, prev, start = [], None, None
    for i, x in enumerate(xs):
        if x is None:
            out.append(None)
            continue
        if start is None:
            start = i
        if i - start < n - 1:
            out.append(None)
        elif i - start == n - 1:
            prev = sum(xs[start:i + 1]) / n
            out.append(prev)
        else:
            prev = prev + (2 / (n + 1)) * (x - prev)
            out.append(prev)
    return out


def ref_rsi(xs, n=14):
    out = [None] * len(xs)
    if len(xs) <= n:
        return out
    up = [max(xs[i] - xs[i - 1], 0) for i in range(1, len(xs))]
    dn = [max(xs[i - 1] - xs[i], 0) for i in range(1, len(xs))]
    avg_up, avg_dn = sum(up[:n]) / n, sum(dn[:n]) / n
    for i in range(n, len(xs)):
        if i > n:
            avg_up = (avg_up * (n - 1) + up[i - 1]) / n
            avg_dn = (avg_dn * (n - 1) + dn[i - 1]) / n
        if avg_up == 0 and avg_dn == 0:
            out[i] = 50.0
        elif avg_dn == 0:
            out[i] = 100.0
        else:
            out[i] = 100 - 100 / (1 + avg_up / avg_dn)
    return out


def ref_macd(xs):
    fast, slow = ref_ema(xs, 12), ref_ema(xs, 26)
    line = [f - s if f is not None and s is not None else None for f, s in zip(fast, slow)]
    signal = ref_ema(line, 9)
    hist = [m - s if m is not None and s is not None else None for m, s in zip(line, signal)]
    return {"macd": line, "signal": signal, "histogram": hist}


def close_enough(a, b):
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert (x is None) == (y is None), (x, y)
        if x is not None:
            assert abs(x - y) <= 1e-9 * max(1.0, abs(x)), (x, y)


ALL_SYMBOLS = [(sid, sym) for sid in ("synthetic-a", "synthetic-b") for sym in paper_market.get(sid)["symbols"]]


@pytest.mark.parametrize("scenario,symbol", ALL_SYMBOLS)
def test_service_matches_the_independent_reference_for_every_symbol(scenario, symbol):
    closes = [b["c"] for b in paper_market.get(scenario)["bars"][symbol]]
    for n in (20, 50):
        close_enough(ind.raw("sma", n, closes)["sma"], ref_sma(closes, n))
    for n in (12, 26):
        close_enough(ind.raw("ema", n, closes)["ema"], ref_ema(closes, n))
    close_enough(ind.raw("rsi", 14, closes)["rsi"], ref_rsi(closes))
    got, want = ind.raw("macd", (12, 26, 9), closes), ref_macd(closes)
    for name in ("macd", "signal", "histogram"):
        close_enough(got[name], want[name])


@pytest.mark.parametrize("timeframe", ["daily", "weekly"])
def test_api_values_match_the_reference_on_a_late_day(client, timeframe):
    state = eng.new_state("synthetic-b")
    for d in range(200):
        state = eng.advance(state, d)
    m = paper_market.get("synthetic-b")
    for symbol in m["symbols"]:
        body = {"state": state, "symbol": symbol, "timeframe": timeframe, "indicators": [
            {"type": "sma", "period": 20}, {"type": "ema", "period": 26}, {"type": "rsi", "period": 14},
            {"type": "macd", "period": [12, 26, 9]}]}
        data = client.post("/api/analysis/indicators", json=body).get_json()["data"]
        if timeframe == "daily":
            closes = [b["c"] for b in m["bars"][symbol][:201]]
        else:
            closes = [w["c"] for w in data["bars"] if w["status"] != "partial"]
        pad = len(data["bars"]) - len(closes)
        want = {"sma": ref_sma(closes, 20), "ema": ref_ema(closes, 26), "rsi": ref_rsi(closes), **ref_macd(closes)}
        for item in data["indicators"]:
            for name, values in item["series"].items():
                ref = [None if v is None else (round(v, 2) if name == "rsi" else round(v / 100, 4)) for v in want[name]]
                assert values == ref + [None] * pad, (symbol, timeframe, name)


# ---- the browser QA scripts are optional, local and zero-cost ----

QA = os.path.join(ROOT, "scripts", "qa")


def qa_files():
    return sorted(f for f in os.listdir(QA) if f.endswith(".mjs"))


def test_qa_scripts_exist_and_need_no_packages():
    assert qa_files() == ["drawings.mjs", "explanations.mjs", "overlays.mjs", "panes.mjs", "run.mjs", "visual_audit.mjs",
                          "workflows.mjs"]
    assert not os.path.exists(os.path.join(ROOT, "package.json")) and not os.path.exists(os.path.join(QA, "package.json"))
    for name in qa_files():
        with open(os.path.join(QA, name), encoding="utf-8") as f:
            code = f.read()
        imports = re.findall(r'^import .* from "([^"]+)";', code, re.M)
        assert all(i.startswith("node:") for i in imports), (name, imports)  # Node built-ins only
        urls = re.findall(r"https?://[^\s\"'`)]+", code)
        assert all(u.startswith("http://127.0.0.1") or u == "https://www.tradingview.com/" for u in urls), (name, urls)


def test_qa_runner_insists_on_zero_cost_demo_mode_and_stops_what_it_started():
    with open(os.path.join(QA, "run.mjs"), encoding="utf-8") as f:
        code = f.read()
    assert 'ZERO_COST_MODE: "1", DATA_MODE: "demo", WARM_CACHE: "0"' in code
    assert 'if (!h.zero_cost_mode || h.data_mode !== "demo") throw' in code
    assert "Something already answers on port" in code and "edge.kill();" in code and "server.kill();" in code


def test_the_app_never_loads_the_qa_scripts():
    with open(os.path.join(ROOT, "templates", "index.html"), encoding="utf-8") as f:
        assert "scripts/qa" not in f.read()
