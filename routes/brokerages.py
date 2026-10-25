# Brokerage Comparison Explorer endpoints. Read-only: the only inputs are which firms, criteria and filters to show.
import logging
import re

from flask import Blueprint, request

from routes.envelope import fail, ok
from services import brokerages
from services.errors import AppError, InvalidRequest

log = logging.getLogger(__name__)
bp = Blueprint("brokerages", __name__, url_prefix="/api/brokerages")
_ID = re.compile(r"^[a-z0-9_-]{1,40}$")


def _ids(name):
    raw = request.args.get(name)
    if raw is None:
        return None
    ids = [p.strip() for p in raw.split(",") if p.strip()]
    if len(ids) > 20 or not all(_ID.match(i) for i in ids):
        raise InvalidRequest(f"The {name} list is not valid.")
    return ids


@bp.get("")
def overview():
    try:
        return ok(brokerages.overview(), None, None)
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("brokerage overview failed")
        return fail(AppError())


@bp.get("/compare")
def compare():
    try:
        raw_quantity = request.args.get("quantity", "1")
        if not raw_quantity.isdigit():
            raise InvalidRequest(f"The example quantity must be a whole number from 1 to {brokerages.MAX_QUANTITY}.")
        result = brokerages.compare(_ids("firms"), _ids("criteria"), _ids("filters"), int(raw_quantity))
        return ok(result, None, None)
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("brokerage compare failed")
        return fail(AppError())
