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

# Zero-cost development mode (default ON): no paid or metered request can be made. Blanking the keys reuses V1's
# existing no-key fallbacks (demo data, fixed explanations, chat unavailable). Set ZERO_COST_MODE=0 to reactivate.
ZERO_COST_MODE = env("ZERO_COST_MODE", "1") != "0"
if ZERO_COST_MODE:
    ANTHROPIC_API_KEY = FINNHUB_API_KEY = FMP_API_KEY = ""
    DATA_MODE = "demo"
    WARM_CACHE = False

# AI Strategy Comparison Lab. Live inference needs ALL of: ZERO_COST_MODE=0, LAB_LIVE_ENABLED=1, a budget above $0,
# the provider's key, the model marked "confirmed" in data/lab_models.json, and confirm_live in the request.
HF_TOKEN = "" if ZERO_COST_MODE else env("HF_TOKEN")
HF_ROUTER_URL = env("HF_ROUTER_URL", "https://router.huggingface.co/v1")
LAB_LIVE_ENABLED = env("LAB_LIVE_ENABLED", "0") == "1"
LAB_DAILY_BUDGET_USD = env("LAB_DAILY_BUDGET_USD", "0")   # string; parsed with Decimal in llm_providers
LAB_MAX_TOKENS = int(env("LAB_MAX_TOKENS", "1200"))
LAB_TIMEOUT_SECONDS = int(env("LAB_TIMEOUT_SECONDS", "45"))
LAB_MODELS_PATH = env("LAB_MODELS_PATH", os.path.join(os.path.dirname(__file__), "data", "lab_models.json"))
LAB_SPEND_LEDGER = env("LAB_SPEND_LEDGER", os.path.join(os.path.dirname(__file__), "data", "lab_spend.json"))

# Paper Trading Lab: key that signs the browser-held practice log. Set PAPER_STATE_SECRET, or a random local key is
# created on first use at PAPER_KEY_PATH (gitignored). Changing the key invalidates existing practice sessions.
PAPER_STATE_SECRET = env("PAPER_STATE_SECRET")
PAPER_KEY_PATH = env("PAPER_KEY_PATH", os.path.join(os.path.dirname(__file__), "data", "paper_state.key"))
MAX_REQUEST_BYTES = 64 * 1024

TTL_QUOTE = 60
TTL_PROFILE = 86400
TTL_FINANCIALS = 86400
TTL_AI = 86400
