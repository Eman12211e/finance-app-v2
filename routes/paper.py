# Paper Trading Lab endpoints. Simulated only: no brokerage, no real orders. The browser sends its signed practice
# log; the server verifies it, applies one action and returns the new signed log plus a derived view.
import logging

from flask import Blueprint, request
from werkzeug.exceptions import RequestEntityTooLarge

from routes.envelope import fail, ok
from services import paper_engine, paper_market
from services.errors import AppError, InvalidRequest, RequestTooLarge

log = logging.getLogger(__name__)
bp = Blueprint("paper", __name__, url_prefix="/api/paper")


def _body():
    try:
        body = request.get_json(silent=True)
    except RequestEntityTooLarge:
        raise RequestTooLarge() from None
    if not isinstance(body, dict):
        raise InvalidRequest()
    return body


def _handle(action):
    try:
        return ok(action(), None, None)
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("paper trading request failed")
        return fail(AppError())


@bp.get("/scenarios")
def scenarios():
    return _handle(lambda: {"scenarios": [paper_market.summary(paper_market.get(s)) for s in paper_market.scenario_ids()],
                            "notices": [paper_engine.SIMULATED_NOTICE, paper_engine.COSTS_NOTICE, paper_engine.FILL_NOTE]})


@bp.post("/new")
def new():
    return _handle(lambda: paper_engine.view(paper_engine.new_state(_body().get("scenario"))))


@bp.post("/view")
def view():
    return _handle(lambda: paper_engine.view(_body().get("state")))


@bp.post("/market")
def market():
    return _handle(lambda: paper_engine.market_bars(_body().get("state")))


@bp.post("/preview")
def preview():
    def run():
        body = _body()
        return paper_engine.preview(body.get("state"), body.get("order"))
    return _handle(run)


@bp.post("/confirm")
def confirm():
    def run():
        body = _body()
        state, duplicate = paper_engine.confirm(body.get("state"), body.get("order"))
        return paper_engine.view(state) | {"duplicate": duplicate}
    return _handle(run)


@bp.post("/cancel")
def cancel():
    def run():
        body = _body()
        return paper_engine.view(paper_engine.cancel(body.get("state"), body.get("order_id")))
    return _handle(run)


@bp.post("/advance")
def advance():
    def run():
        body = _body()
        return paper_engine.view(paper_engine.advance(body.get("state"), body.get("expected_day")))
    return _handle(run)
