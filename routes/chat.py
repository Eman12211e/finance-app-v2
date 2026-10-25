# Owner: Agent C.
import logging

from flask import Blueprint, request

from routes.envelope import fail, ok
from services import ai_service
from services.errors import AppError, InvalidRequest
from services.prompts import CHAT_FALLBACK_ADVICE, CHECKLIST_TRIGGER
from services.validation import validate_profile

log = logging.getLogger(__name__)
bp = Blueprint("chat", __name__, url_prefix="/api")


@bp.post("/chat")
def chat():
    try:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise InvalidRequest()
        message = body.get("message")
        message = message.strip() if isinstance(message, str) else ""
        if not 1 <= len(message) <= 500:
            raise InvalidRequest("Please type a question of 1 to 500 characters.")
        profile = body.get("profile") if isinstance(body.get("profile"), dict) else {}
        profile = validate_profile(profile.get("age_range"), profile.get("risk"))
        history = body.get("history") if isinstance(body.get("history"), list) else []
        context = body.get("context") if isinstance(body.get("context"), dict) else None

        reply = ai_service.chat(message, history, profile, context)
        show_link = bool(CHECKLIST_TRIGGER.search(message)) or reply == CHAT_FALLBACK_ADVICE

        source = context.get("source") if context else None
        as_of = context.get("as_of") if context else None
        return ok(
            {"reply": reply, "show_checklist_link": show_link},
            source if source in ("live", "cache", "demo") else None,
            as_of if isinstance(as_of, str) and source in ("live", "cache", "demo") else None,
        )
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("chat failed")
        return fail(AppError())
