# Owner: Integrator. Optional Sentiment Explorer endpoints.
import logging

from flask import Blueprint, request

import config
from routes.envelope import fail, ok
from services import sentiment_service
from services.errors import AppError, InvalidRequest

log = logging.getLogger(__name__)
bp = Blueprint("sentiment", __name__, url_prefix="/api")


@bp.get("/sentiment/statements")
def statements():
    try:
        data = sentiment_service.statements()
        return ok({"enabled": config.SENTIMENT_ENABLED, "model": config.SENTIMENT_MODEL,
                   "note": data["note"], "statements": data["statements"]}, None, None)
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("sentiment statements failed")
        return fail(AppError())


@bp.post("/sentiment")
def classify():
    try:
        body = request.get_json(silent=True)
        statement_id = body.get("statement_id") if isinstance(body, dict) else None
        if not isinstance(statement_id, str) or not statement_id:
            raise InvalidRequest("Please choose one of the example statements.")
        return ok(sentiment_service.classify(statement_id), None, None)
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("sentiment classify failed")
        return fail(AppError())
