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
})
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from services import cache  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client():
    return create_app().test_client()
