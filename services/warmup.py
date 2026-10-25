# Owner: Agent E. Pre-loads the cache for the demo tickers in a background thread when WARM_CACHE=1.
import logging
import threading
import time

import config
from services import ai_service, earnings_service, market_data

log = logging.getLogger(__name__)


def _warm():
    start, done = time.monotonic(), 0
    for ticker in config.DEMO_TICKERS:
        try:
            market_data.get_snapshot(ticker)
            financials, source, _ = market_data.get_financials(ticker)
            facts = earnings_service.build_facts(financials, "demo" if source == "demo" else "live")
            ai_service.explain_earnings(facts, config.DEFAULT_PROFILE)
            done += 1
        except Exception:
            log.exception("warmup failed for ticker=%s", ticker)
    log.info("warmup done: %d/%d tickers in %.1fs", done, len(config.DEMO_TICKERS), time.monotonic() - start)


def run_if_enabled(app) -> None:
    if not config.WARM_CACHE:
        log.info("warmup disabled")
        return
    threading.Thread(target=_warm, name="warmup", daemon=True).start()
