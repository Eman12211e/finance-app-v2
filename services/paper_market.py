"""Paper Trading Lab market data: fixed synthetic scenarios in data/paper/scenarios/*.json.
Callers only ever get bars up to the current replay day; future bars never leave this module."""
import json
import os

from services.errors import InvalidRequest

SCENARIO_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "paper", "scenarios")
_scenarios = {}


def scenario_ids():
    return sorted(name[:-5] for name in os.listdir(SCENARIO_DIR) if name.endswith(".json"))


def get(scenario_id):
    if scenario_id not in scenario_ids():
        raise InvalidRequest("Unknown practice scenario.")
    if scenario_id not in _scenarios:
        with open(os.path.join(SCENARIO_DIR, f"{scenario_id}.json"), encoding="utf-8") as f:
            _scenarios[scenario_id] = json.load(f)
    return _scenarios[scenario_id]


def last_day(market):
    return len(market["dates"]) - 1


def summary(market):
    return {k: market[k] for k in ("id", "label", "kind", "notice", "timeframe", "symbols")} | {
        "days": len(market["dates"]), "first_date": market["dates"][0]}


def bars_until(market, day):
    """Bars for every symbol from the first day up to and including `day`. Never later."""
    if not 0 <= day <= last_day(market):
        raise InvalidRequest("That simulated day is outside the scenario.")
    return {"dates": market["dates"][:day + 1],
            "bars": {s: series[:day + 1] for s, series in market["bars"].items()}}


def bar(market, symbol, day):
    return market["bars"][symbol][day]
