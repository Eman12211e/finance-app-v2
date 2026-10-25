"""ONLY file that calls FMP. Returns parsed JSON; raises ProviderError on any failure."""
import logging

import requests

import config
from services.errors import ProviderError

log = logging.getLogger(__name__)
BASE = "https://financialmodelingprep.com/stable"


def _get(endpoint, path, params):
    if not config.FMP_API_KEY:
        raise ProviderError()
    try:
        resp = requests.get(f"{BASE}{path}", params={**params, "apikey": config.FMP_API_KEY}, timeout=8)
    except requests.RequestException as exc:
        # exception text can contain the URL with the key, so log only its type
        log.warning("fmp endpoint=%s failed: %s", endpoint, type(exc).__name__)
        raise ProviderError() from None
    try:
        body = resp.json()
    except ValueError:
        body = None
    if resp.status_code != 200 or not body or (isinstance(body, dict) and "Error Message" in body):
        log.warning("fmp endpoint=%s status=%s no usable data", endpoint, resp.status_code)
        raise ProviderError()
    return body


def get_profile(t):
    return _get("profile", "/profile", {"symbol": t})


def get_income_statement_quarterly(t):
    return _get("income_statement_q", "/income-statement", {"symbol": t, "period": "quarter", "limit": 5})


def get_balance_sheet_quarterly(t):
    return _get("balance_sheet_q", "/balance-sheet-statement", {"symbol": t, "period": "quarter", "limit": 5})


def get_dividends(t):
    return _get("dividends", "/dividends", {"symbol": t})
