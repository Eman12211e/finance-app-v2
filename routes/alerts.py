# Owner: Agent D.
import logging

from flask import Blueprint, request

from routes.envelope import fail, ok
from services import alerts_service, market_data
from services.errors import AppError, InvalidRequest
from services.validation import validate_ticker

log = logging.getLogger(__name__)
bp = Blueprint("alerts", __name__, url_prefix="/api")
MAX_TICKERS = 20  # watchlist holds 8; this only bounds untrusted input


@bp.get("/alerts")
def alerts():
    try:
        parts = [p.strip() for p in request.args.get("tickers", "").split(",") if p.strip()]
        if not parts:
            raise InvalidRequest("Please include at least one ticker.")
        if len(parts) > MAX_TICKERS:
            raise InvalidRequest(f"Please send at most {MAX_TICKERS} tickers.")
        tickers = list(dict.fromkeys(validate_ticker(p) for p in parts))
        return ok({"alerts": alerts_service.build_alerts(tickers)}, "demo", market_data.load_demo()["generated_at"])
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("alerts failed")
        return fail(AppError())
