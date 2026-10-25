# AI Strategy Comparison Lab endpoints. Simulated by default; live needs every gate plus an explicit confirmation.
import logging

from flask import Blueprint, request

import config
from routes.envelope import fail, ok
from services import llm_providers, strategy_lab
from services.errors import AppError, InvalidRequest
from services.prompts import LAB_SCENARIOS
from services.validation import validate_ticker

log = logging.getLogger(__name__)
bp = Blueprint("lab", __name__, url_prefix="/api/lab")


@bp.get("/config")
def lab_config():
    try:
        reg = llm_providers.registry()
        models = [{**strategy_lab.public_model(m), "context_tokens": m["context_tokens"],
                   "price_in_per_m": m["price_in_per_m"], "price_out_per_m": m["price_out_per_m"],
                   "live_blocked_reasons": llm_providers.live_block_reasons(m)} for m in reg["models"]]
        return ok({
            "zero_cost_mode": config.ZERO_COST_MODE,
            "live_enabled": config.LAB_LIVE_ENABLED,
            "live_available": all(not m["live_blocked_reasons"] for m in models),
            "daily_budget_usd": str(llm_providers.daily_budget_usd()),
            "spent_today_usd": str(llm_providers.spent_today_usd()),
            "registry_verified_on": reg["verified_on"],
            "registry_verification": reg["verification"],
            "simulated_label": strategy_lab.SIMULATED_LABEL,
            "scenarios": [{"key": k, **v} for k, v in LAB_SCENARIOS.items()],
            "tickers": config.DEMO_TICKERS,
            "models": models,
            "criteria": strategy_lab.CRITERIA,
        }, None, None)
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("lab config failed")
        return fail(AppError())


@bp.post("/compare")
def compare():
    try:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise InvalidRequest()
        ticker = validate_ticker(body.get("ticker"))
        models = body.get("models")
        if models is not None and not (isinstance(models, list) and models and all(isinstance(m, str) for m in models)):
            raise InvalidRequest("Please choose at least one model.")
        live = body.get("live") is True
        if live and body.get("confirm_live") is not True:
            raise InvalidRequest("A live run must be confirmed after reviewing its cost estimate.")
        result = strategy_lab.compare(ticker, body.get("scenario"), models, live=live)
        return ok(result, result["evidence"]["source"], result["evidence"]["as_of"])
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("lab compare failed")
        return fail(AppError())
