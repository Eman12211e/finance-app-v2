import logging

from flask import Flask, render_template

import config
from routes import alerts, chat, earnings, sentiment, stocks
from routes.envelope import ok
from services import warmup


def create_app():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    app = Flask(__name__)
    for module in (stocks, earnings, chat, alerts, sentiment):
        app.register_blueprint(module.bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return ok(
            {
                "status": "ok",
                "data_mode": config.DATA_MODE,
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
