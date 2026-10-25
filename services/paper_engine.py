"""Paper Trading Lab engine: a self-contained, cash-only, long-only practice simulator in integer cents and whole shares.
The browser keeps only a signed order log. Every request verifies the signature and re-derives cash, positions and
profit/loss from that log and the fixed scenario, so balances or holdings sent by a browser are never trusted.
No real orders, no brokerage, no market data feed: this is an educational simulation."""
import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from decimal import ROUND_HALF_EVEN, Decimal

import config
from services import paper_market
from services.errors import InvalidRequest, InvalidState
from services.formatting import cents_display

SCHEMA = 1
START_CASH_CENTS = 1_000_000  # $10,000.00 of fictional cash
MAX_SHARES = 100_000
MAX_ORDERS = 200  # keeps the signed log well under the request-size limit; reset to start again
ORDER_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
STATE_KEYS = {"schema", "scenario", "day", "ended", "orders", "sig"}
ORDER_KEYS = {"id", "symbol", "side", "shares", "placed_day", "status", "reason", "fill_day"}
STATUSES = ("pending", "filled", "rejected", "cancelled")
SIMULATED_NOTICE = "Simulated practice trading with synthetic prices. No real securities are bought or sold."
COSTS_NOTICE = ("This basic simulator leaves out real-world costs and effects: commissions and fees, the bid-ask "
                "spread, slippage and market impact.")
MIN_SECRET_CHARS = 32
_keys = {}  # (PAPER_STATE_SECRET, PAPER_KEY_PATH) -> key bytes
_key_lock = threading.Lock()
FILL_NOTE = "Orders fill at the next simulated day's opening price, which can differ from today's close."


# ---- signing (the only thing that lets a stateless server trust a browser-held log) ----

def _key_file(path):
    """Reads the local key, creating it on first use. The key is written to a temporary file and linked into place,
    so no reader can ever see a partly written or empty key, and an existing key is never overwritten."""
    if not os.path.exists(path):
        tmp = f"{path}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(32))
        try:
            os.link(tmp, path)
        except FileExistsError:
            pass  # another request created it first; use theirs
        finally:
            os.remove(tmp)
    with open(path, encoding="utf-8") as f:
        key = f.read().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        raise RuntimeError(f"The paper trading key file {path} is damaged. Delete it to create a new one "
                           "(existing practice sessions will end).")
    return key


def _secret():
    """The signing key: PAPER_STATE_SECRET if set (at least 32 characters), otherwise the local key file.
    Loaded once per setting under a lock, so concurrent first requests always agree on one key."""
    setting = (config.PAPER_STATE_SECRET, config.PAPER_KEY_PATH)
    with _key_lock:
        if setting not in _keys:
            if config.PAPER_STATE_SECRET and len(config.PAPER_STATE_SECRET) < MIN_SECRET_CHARS:
                raise RuntimeError(f"PAPER_STATE_SECRET must be at least {MIN_SECRET_CHARS} characters.")
            _keys[setting] = (config.PAPER_STATE_SECRET or _key_file(config.PAPER_KEY_PATH)).encode()
        return _keys[setting]


def _signature(body):
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hmac.new(_secret(), canonical.encode(), hashlib.sha256).hexdigest()


def _sign(body):
    return {**body, "sig": _signature(body)}


def _is_int(value, low, high):
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def verify(state):
    """Returns the verified state body (without sig) and its market, or raises InvalidState."""
    if not isinstance(state, dict) or set(state) != STATE_KEYS or not isinstance(state["sig"], str):
        raise InvalidState()
    body = copy.deepcopy({k: v for k, v in state.items() if k != "sig"})  # actions must never change the caller's state
    if not hmac.compare_digest(state["sig"], _signature(body)):
        raise InvalidState()
    try:  # defence in depth: a correctly signed state must also be well formed
        market = paper_market.get(body["scenario"])
    except InvalidRequest:
        raise InvalidState() from None
    last = paper_market.last_day(market)
    orders = body["orders"]
    ok = (body["schema"] == SCHEMA and _is_int(body["day"], 0, last) and isinstance(body["ended"], bool)
          and isinstance(orders, list) and len(orders) <= MAX_ORDERS)
    ids = set()
    for o in orders if ok else []:
        ok = (isinstance(o, dict) and set(o) == ORDER_KEYS and isinstance(o["id"], str) and ORDER_ID.match(o["id"])
              and o["id"] not in ids and o["symbol"] in market["symbols"] and o["side"] in ("buy", "sell")
              and _is_int(o["shares"], 1, MAX_SHARES) and _is_int(o["placed_day"], 0, body["day"])
              and o["status"] in STATUSES
              and (o["reason"] is None if o["status"] in ("pending", "filled") else isinstance(o["reason"], str))
              and (o["fill_day"] is None if o["status"] != "filled" else _is_int(o["fill_day"], o["placed_day"] + 1, body["day"])))
        if not ok:
            break
        ids.add(o["id"])
    if not ok:
        raise InvalidState()
    return body, market


def new_state(scenario_id):
    paper_market.get(scenario_id)
    return _sign({"schema": SCHEMA, "scenario": scenario_id, "day": 0, "ended": False, "orders": []})


# ---- deriving the portfolio from the log ----

def _half_even(numerator, denominator):
    return int((Decimal(numerator) / Decimal(denominator)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _apply_fill(book, order, price):
    """Applies one filled order to {cash, positions, realized}; returns the transaction record."""
    amount = order["shares"] * price
    pos = book["positions"].setdefault(order["symbol"], {"shares": 0, "cost_basis_cents": 0})
    realized = None
    if order["side"] == "buy":
        if amount > book["cash"]:
            raise InvalidState()
        book["cash"] -= amount
        pos["shares"] += order["shares"]
        pos["cost_basis_cents"] += amount
    else:
        held = pos["shares"]
        if order["shares"] > held:
            raise InvalidState()
        # proportional basis, rounded down; selling everything removes the whole basis so no cents are left behind
        portion = pos["cost_basis_cents"] if order["shares"] == held else pos["cost_basis_cents"] * order["shares"] // held
        realized = amount - portion
        book["cash"] += amount
        book["realized"] += realized
        pos["shares"] -= order["shares"]
        pos["cost_basis_cents"] -= portion
    if pos["shares"] == 0:
        del book["positions"][order["symbol"]]
    return {"order_id": order["id"], "symbol": order["symbol"], "side": order["side"], "shares": order["shares"],
            "price_cents": price, "amount_cents": amount, "realized_pl_cents": realized, "cash_after_cents": book["cash"]}


def _book(body, market):
    """Replays every filled order in fill order (fill day, then log order)."""
    book = {"cash": START_CASH_CENTS, "positions": {}, "realized": 0, "transactions": []}
    filled = sorted((o for o in body["orders"] if o["status"] == "filled"),
                    key=lambda o: (o["fill_day"], body["orders"].index(o)))
    for o in filled:
        tx = _apply_fill(book, o, paper_market.bar(market, o["symbol"], o["fill_day"])["o"])
        book["transactions"].append({**tx, "day": o["fill_day"], "date": market["dates"][o["fill_day"]]})
    return book


def portfolio(body, market):
    book = _book(body, market)
    day = body["day"]
    positions, unrealized_total, value = [], 0, book["cash"]
    for symbol in sorted(book["positions"]):
        pos = book["positions"][symbol]
        close = paper_market.bar(market, symbol, day)["c"]
        market_value = pos["shares"] * close
        unrealized = market_value - pos["cost_basis_cents"]
        unrealized_total += unrealized
        value += market_value
        positions.append({"symbol": symbol, "shares": pos["shares"], "cost_basis_cents": pos["cost_basis_cents"],
                          "average_cost_cents": _half_even(pos["cost_basis_cents"], pos["shares"]),
                          "close_cents": close, "market_value_cents": market_value, "unrealized_pl_cents": unrealized})
    return {"start_cash_cents": START_CASH_CENTS, "cash_cents": book["cash"], "positions": positions,
            "realized_pl_cents": book["realized"], "unrealized_pl_cents": unrealized_total,
            "portfolio_value_cents": value, "total_pl_cents": value - START_CASH_CENTS,
            "transactions": book["transactions"]}


# ---- new orders ----

def _parse_order(order, market):
    if not isinstance(order, dict):
        raise InvalidRequest("The order is missing.")
    symbol, side, shares = order.get("symbol"), order.get("side"), order.get("shares")
    problems = []
    if symbol not in market["symbols"]:
        problems.append({"code": "unsupported_symbol", "message": "That symbol is not part of this practice scenario."})
    if side not in ("buy", "sell"):
        problems.append({"code": "invalid_side", "message": "Choose buy or sell."})
    if not _is_int(shares, 1, MAX_SHARES):
        problems.append({"code": "invalid_quantity",
                         "message": f"Enter a whole number of shares from 1 to {MAX_SHARES:,}."})
    return symbol, side, shares, problems


def _check_order(body, market, symbol, side, shares):
    """Problems with placing this order now, given pending orders. Assumes symbol/side/shares are valid."""
    if body["ended"]:
        return [{"code": "scenario_ended", "message": "This practice scenario has ended. Reset to start again."}]
    if len(body["orders"]) >= MAX_ORDERS:
        return [{"code": "order_limit", "message": f"This session has reached {MAX_ORDERS} orders. Reset to start again."}]
    day, book = body["day"], _book(body, market)
    pending = [o for o in body["orders"] if o["status"] == "pending"]
    if side == "buy":
        reserved = sum(o["shares"] * paper_market.bar(market, o["symbol"], day)["c"] for o in pending if o["side"] == "buy")
        estimate = shares * paper_market.bar(market, symbol, day)["c"]
        if estimate > book["cash"] - reserved:
            return [{"code": "insufficient_cash",
                     "message": f"Not enough fictional cash: this order is about {cents_display(estimate)} at today's close, "
                                f"and {cents_display(max(book['cash'] - reserved, 0))} is available after pending buys."}]
    else:
        held = book["positions"].get(symbol, {}).get("shares", 0)
        selling = sum(o["shares"] for o in pending if o["side"] == "sell" and o["symbol"] == symbol)
        if shares > held - selling:
            return [{"code": "insufficient_shares",
                     "message": f"You can sell at most {max(held - selling, 0)} shares of {symbol}, counting pending sells."}]
    return []


def preview(state, order):
    body, market = verify(state)
    symbol, side, shares, problems = _parse_order(order, market)
    problems = problems or _check_order(body, market, symbol, side, shares)
    result = {"ok": not problems, "problems": problems, "fill_note": FILL_NOTE}
    if not problems:
        close = paper_market.bar(market, symbol, body["day"])["c"]
        result.update(symbol=symbol, side=side, shares=shares, reference_close_cents=close,
                      estimated_amount_cents=shares * close)
        if body["day"] == paper_market.last_day(market):
            result["warning"] = ("This is the last simulated day. There is no next open, so this order will be "
                                 "cancelled when the scenario ends.")
    return result


def confirm(state, order):
    """Adds a pending order. Repeating the same order id returns the state unchanged (no double submission)."""
    body, market = verify(state)
    order_id = order.get("id") if isinstance(order, dict) else None
    if not isinstance(order_id, str) or not ORDER_ID.match(order_id):
        raise InvalidRequest("Each order needs a unique id of 8 to 64 letters, digits, - or _.")
    if any(o["id"] == order_id for o in body["orders"]):
        return _sign(body), True
    symbol, side, shares, problems = _parse_order(order, market)
    problems = problems or _check_order(body, market, symbol, side, shares)
    if problems:
        raise InvalidRequest(" ".join(p["message"] for p in problems))
    body["orders"].append({"id": order_id, "symbol": symbol, "side": side, "shares": shares,
                           "placed_day": body["day"], "status": "pending", "reason": None, "fill_day": None})
    return _sign(body), False


def cancel(state, order_id):
    body, _ = verify(state)
    order = next((o for o in body["orders"] if o["id"] == order_id), None)
    if order is None:
        raise InvalidRequest("That order is not in this session.")
    if order["status"] == "filled":
        raise InvalidRequest("That order has already filled and cannot be cancelled.")
    if order["status"] == "pending":
        order.update(status="cancelled", reason="Cancelled by you before it filled.")
    return _sign(body)  # cancelling an already cancelled or rejected order changes nothing


def advance(state, expected_day):
    """Moves to the next simulated day and fills pending orders at its opening price, in the order they were placed.
    Deterministic: the same state always gives the same result. A stale expected_day is refused, so one click
    cannot advance twice. On the last day it ends the scenario and cancels anything still pending."""
    body, market = verify(state)
    if not _is_int(expected_day, 0, paper_market.last_day(market)) or expected_day != body["day"]:
        raise InvalidRequest("This session has already moved past that day. Refresh it before advancing again.")
    if body["ended"]:
        raise InvalidRequest("This practice scenario has ended. Reset to start again.")
    pending = [o for o in body["orders"] if o["status"] == "pending"]
    if body["day"] == paper_market.last_day(market):
        for o in pending:
            o.update(status="cancelled", reason="The scenario ended before the next simulated open, so this order could not fill.")
        body["ended"] = True
        return _sign(body)
    nxt = body["day"] + 1
    book = _book(body, market)
    for o in pending:
        price = paper_market.bar(market, o["symbol"], nxt)["o"]
        held = book["positions"].get(o["symbol"], {}).get("shares", 0)
        if o["side"] == "buy" and o["shares"] * price > book["cash"]:
            o.update(status="rejected", reason=f"Not enough fictional cash at the opening price of {cents_display(price)}: "
                                               f"needed {cents_display(o['shares'] * price)}, had {cents_display(book['cash'])}.")
        elif o["side"] == "sell" and o["shares"] > held:
            o.update(status="rejected", reason=f"Not enough shares to sell: held {held}.")
        else:
            o.update(status="filled", fill_day=nxt)
            _apply_fill(book, o, price)
    body["day"] = nxt
    return _sign(body)


def view(state):
    """Everything the interface needs about a verified session. Only bars up to the current day are used."""
    body, market = verify(state)
    day = body["day"]
    return {
        "state": state,
        "scenario": paper_market.summary(market),
        "day": {"index": day, "date": market["dates"][day], "is_last": day == paper_market.last_day(market),
                "ended": body["ended"]},
        "quotes": {s: {"close_cents": paper_market.bar(market, s, day)["c"], "date": market["dates"][day]}
                   for s in market["symbols"]},
        "portfolio": portfolio(body, market),
        "orders": body["orders"],
        "notices": [SIMULATED_NOTICE, COSTS_NOTICE, FILL_NOTE, market["notice"]],
    }


def market_bars(state):
    body, market = verify(state)
    return paper_market.bars_until(market, body["day"]) | {"notice": market["notice"]}
