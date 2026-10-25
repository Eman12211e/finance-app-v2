import os

from dotenv import load_dotenv

load_dotenv()


def env(name, default=""):
    return os.getenv(name, default)


ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
FINNHUB_API_KEY = env("FINNHUB_API_KEY")
FMP_API_KEY = env("FMP_API_KEY")

CLAUDE_MODEL = "claude-sonnet-5-5"
AI_TIMEOUT_SECONDS = 20
AI_MAX_TOKENS_CHAT = 300
AI_MAX_TOKENS_EARNINGS = 900
CHAT_HISTORY_LIMIT = 6

DATA_MODE = env("DATA_MODE", "demo")      # "demo" | "live"
WARM_CACHE = env("WARM_CACHE", "0") == "1"

DEMO_TICKERS = ["AAPL", "MSFT", "KO", "NVDA", "VOO"]
ETF_TICKERS = ["VOO"]

ALLOWED_AGE_RANGES = ["18-24", "25-34", "35-49", "50+"]
ALLOWED_RISK = ["low", "medium", "high"]
DEFAULT_PROFILE = {"age_range": "25-34", "risk": "medium"}   # used by warmup only

# Optional Sentiment Explorer (local FinBERT, requirements-sentiment.txt). Off unless SENTIMENT_ENABLED=1.
SENTIMENT_ENABLED = env("SENTIMENT_ENABLED", "0") == "1"
SENTIMENT_MODEL = "ProsusAI/finbert"

TTL_QUOTE = 60
TTL_PROFILE = 86400
TTL_FINANCIALS = 86400
TTL_AI = 86400
