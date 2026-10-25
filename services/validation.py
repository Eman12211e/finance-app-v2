import re

import config
from services.errors import InvalidProfile, InvalidTicker

_TICKER_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")


def validate_ticker(raw):
    ticker = (raw or "").strip().upper()
    if not _TICKER_RE.match(ticker):
        raise InvalidTicker()
    return ticker


def validate_profile(age_range, risk):
    if age_range not in config.ALLOWED_AGE_RANGES or risk not in config.ALLOWED_RISK:
        raise InvalidProfile()
    return {"age_range": age_range, "risk": risk}
