from flask import jsonify


def ok(data, source, as_of):
    return jsonify({"ok": True, "data": data, "source": source, "as_of": as_of, "error": None}), 200


def fail(error):
    body = {
        "ok": False,
        "data": None,
        "source": None,
        "as_of": None,
        "error": {"code": error.code, "message": error.message},
    }
    return jsonify(body), error.http_status
