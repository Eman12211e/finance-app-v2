"""ONLY file that calls Finnhub. Returns parsed JSON; raises ProviderError on any failure."""
import logging
from datetime import date, timedelta

import requests

import config
from services.errors import ProviderError

log = logging.getLogger(__name__)
BASE = "https://finnhub.io/api/v1"


def _get(endpoint, path, params):
    if not config.FINNHUB_API_KEY:
        raise ProviderError()
    try:
        resp = requests.get(f"{BASE}{path}", params={**params, "token": config.FINNHUB_API_KEY}, timeout=8)
    except requests.RequestException as exc:
        # exception text can contain the URL with the key, so log only its type
        log.warning("finnhub endpoint=%s failed: %s", endpoint, type(exc).__name__)
        raise ProviderError() from None
    try:
        body = resp.json()
    except ValueError:
        body = None
    if resp.status_code != 200 or not body or (isinstance(body, dict) and "error" in body):
        log.warning("finnhub endpoint=%s status=%s no usable data", endpoint, resp.status_code)
        raise ProviderError()
    return body


def get_quote(t):
    body = _get("quote", "/quote", {"symbol": t})
    if not body.get("c"):  # unknown symbols return all zeros
        log.warning("finnhub endpoint=quote ticker=%s empty quote", t)
        raise ProviderError()
    return body


def get_profile(t):
    return _get("profile2", "/stock/profile2", {"symbol": t})


def get_earnings(t):
    return _get("earnings", "/stock/earnings", {"symbol": t})


def get_earnings_calendar(t):
    today = date.today()
    return _get("calendar_earnings", "/calendar/earnings",
                {"symbol": t, "from": today.isoformat(), "to": (today + timedelta(days=120)).isoformat()})
