import os
import sys

# Must be set before config is imported. load_dotenv does not override existing env vars,
# even empty ones, so tests never see real keys from .env and never call paid APIs.
os.environ.update({
    "ANTHROPIC_API_KEY": "",
    "FINNHUB_API_KEY": "",
    "FMP_API_KEY": "",
    "DATA_MODE": "demo",
    "WARM_CACHE": "0",
    "SENTIMENT_ENABLED": "0",
    "ZERO_COST_MODE": "1",
    "HF_TOKEN": "",
    "LAB_LIVE_ENABLED": "0",
    "LAB_DAILY_BUDGET_USD": "0",
})
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import anthropic  # noqa: E402
import pytest  # noqa: E402
import requests  # noqa: E402

from app import create_app  # noqa: E402
from services import cache  # noqa: E402


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """Zero-cost guard: any real HTTP or Anthropic call fails the test. Tests that need one install a fake."""
    def blocked(*a, **k):
        raise AssertionError("real network or AI call attempted in a test")
    monkeypatch.setattr(requests, "get", blocked)
    monkeypatch.setattr(requests, "post", blocked)
    monkeypatch.setattr(anthropic, "Anthropic", blocked)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client():
    return create_app().test_client()
