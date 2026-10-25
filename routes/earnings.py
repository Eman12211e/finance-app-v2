# Owner: Agent A.
import logging

from flask import Blueprint, request

from routes.envelope import fail, ok
from services import ai_service, earnings_service, market_data
from services.errors import AppError
from services.validation import validate_profile, validate_ticker

log = logging.getLogger(__name__)
bp = Blueprint("earnings", __name__, url_prefix="/api")


@bp.get("/stocks/<ticker>/earnings")
def earnings(ticker):
    try:
        ticker = validate_ticker(ticker)
        profile = validate_profile(request.args.get("age_range"), request.args.get("risk"))
        financials, source, as_of = market_data.get_financials(ticker)
        facts = earnings_service.build_facts(financials, "demo" if source == "demo" else "live")
        explanations, explanation_source = ai_service.explain_earnings(facts, profile)
        return ok(earnings_service.attach_explanations(facts, explanations, explanation_source), source, as_of)
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("earnings failed for ticker=%s", ticker)
        return fail(AppError())
