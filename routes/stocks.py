# Owner: Agent A.
import logging

from flask import Blueprint

from routes.envelope import fail, ok
from services import market_data
from services.errors import AppError
from services.validation import validate_ticker

log = logging.getLogger(__name__)
bp = Blueprint("stocks", __name__, url_prefix="/api")


@bp.get("/stocks/<ticker>/snapshot")
def snapshot(ticker):
    try:
        data, source, as_of = market_data.get_snapshot(validate_ticker(ticker))
        return ok(data, source, as_of)
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("snapshot failed for ticker=%s", ticker)
        return fail(AppError())
