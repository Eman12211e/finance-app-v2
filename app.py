import logging

from flask import Flask, render_template, request

import config
from routes import alerts, analysis, backtest, brokerages, chat, documents, earnings, lab, paper, sentiment, stocks
from routes.envelope import fail, ok
from services.errors import AppError, MethodNotAllowed, NotFound, RequestTooLarge
from services import warmup

# Everything the page uses is served from this app (scripts, styles, fonts, the vendored chart library); the only
# image is the empty data: favicon. Scripts and styles set through the DOM are allowed; inline <script>, <style>,
# style="" and on*="" are not (the page has none). It cannot be framed, and outbound links send no referrer.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
SECURITY_HEADERS = {"Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
                    "Referrer-Policy": "no-referrer", "Cross-Origin-Opener-Policy": "same-origin"}


def create_app():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    for problem in config.PROBLEMS:  # serve.py refuses to start on these; development carries on with the defaults
        logging.getLogger(__name__).warning("setting ignored: %s", problem)
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_REQUEST_BYTES
    for module in (stocks, earnings, chat, alerts, sentiment, lab, documents, brokerages, paper, analysis, backtest):
        app.register_blueprint(module.bp)

    @app.errorhandler(413)
    def too_large(_):
        return fail(RequestTooLarge())

    @app.before_request
    def refuse_large_bodies():  # before any route runs: some older routes' broad except turned this into a 500
        if request.content_length is not None and request.content_length > config.MAX_REQUEST_BYTES:
            return fail(RequestTooLarge())

    # /api/ always answers in the JSON envelope, so the page can tell "wrong address" from "no connection"
    @app.errorhandler(404)
    def not_found(err):
        return fail(NotFound()) if request.path.startswith("/api/") else err

    @app.errorhandler(405)
    def method_not_allowed(err):
        if not request.path.startswith("/api/"):
            return err
        body, status = fail(MethodNotAllowed())
        return body, status, {"Allow": ", ".join(sorted(err.valid_methods or []))}

    @app.errorhandler(500)
    def internal_error(err):  # routes catch their own errors; this is the last net, details stay in the log
        return fail(AppError()) if request.path.startswith("/api/") else err

    @app.after_request
    def security_headers(resp):
        for name, value in SECURITY_HEADERS.items():
            resp.headers.setdefault(name, value)
        return resp

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return ok(
            {
                "status": "ok",
                "data_mode": config.DATA_MODE,
                "zero_cost_mode": config.ZERO_COST_MODE,
                "keys_present": {
                    "anthropic": bool(config.ANTHROPIC_API_KEY),
                    "finnhub": bool(config.FINNHUB_API_KEY),
                    "fmp": bool(config.FMP_API_KEY),
                },
            },
            None,
            None,
        )

    warmup.run_if_enabled(app)
    return app


if __name__ == "__main__":
    create_app().run(port=5000, debug=False)
