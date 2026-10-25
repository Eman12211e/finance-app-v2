# Understand Before You Sign endpoints. Read-only: there is deliberately no route that accepts user data.
import logging
import re

from flask import Blueprint

from routes.envelope import fail, ok
from services import documents
from services.errors import AppError, InvalidRequest

log = logging.getLogger(__name__)
bp = Blueprint("documents", __name__, url_prefix="/api/documents")
_DOC_ID = re.compile(r"^[a-z0-9-]{1,40}$")


@bp.get("")
def list_documents():
    try:
        return ok({"documents": documents.list_documents()}, None, None)
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("document list failed")
        return fail(AppError())


@bp.get("/<doc_id>")
def get_document(doc_id):
    try:
        if not _DOC_ID.match(doc_id):
            raise InvalidRequest("That document id is not valid.")
        return ok(documents.get_document(doc_id), None, None)
    except AppError as err:
        return fail(err)
    except Exception:
        log.exception("document get failed for id=%s", doc_id)
        return fail(AppError())
