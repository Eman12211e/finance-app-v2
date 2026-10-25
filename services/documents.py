"""Understand Before You Sign: human-written document guides in data/documents/*.json.
Static content only: no AI, no user input, nothing stored."""
import json
import os

from services.errors import DataNotAvailable

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "documents")
# The order people usually meet these documents when opening an account.
ORDER = ("form-crs", "brokerage-agreement", "margin-agreement", "form-w9", "identity-verification")
_docs = None


def _load():
    global _docs
    if _docs is None:
        docs = {}
        for doc_id in ORDER:
            with open(os.path.join(DOCS_DIR, f"{doc_id}.json"), encoding="utf-8") as f:
                docs[doc_id] = json.load(f)
        _docs = docs
    return _docs


def list_documents():
    return [{"id": d["id"], "title": d["title"], "summary": d["summary"], "when_you_see_it": d["when_you_see_it"],
             "origins": sorted({s["origin"] for s in d["sections"]}), "section_count": len(d["sections"])}
            for d in _load().values()]


def get_document(doc_id):
    doc = _load().get(doc_id)
    if doc is None:
        raise DataNotAvailable("That document guide does not exist.")
    return doc
