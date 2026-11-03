"""Release start-up check (P6 step 3): everything that would make a release start fail later, found before serving.
Reads only: it never creates the signing key, writes a file or opens a port. Used by `python serve.py` and
`python serve.py --check`. Development (`python app.py`) logs the same settings problems as warnings."""
import json
import os

import config
from services import paper_market, strategy_guide

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LOCAL_ONLY = ("lab_spend.json",)  # written by the app itself on first use; may not exist yet
REQUIRED = ("demo_stocks.json", "brokerage_criteria.json", "indicator_guide.json", "strategy_guide.json",
            "lab_models.json", "sentiment_statements.json", "paper/scenarios/synthetic-a.json",
            "paper/scenarios/synthetic-b.json")


def check(data_dir=DATA_DIR):
    """Plain-language problems; an empty list means ready."""
    problems = list(config.PROBLEMS)
    for name in REQUIRED:
        if not os.path.isfile(os.path.join(data_dir, *name.split("/"))):
            problems.append(f"data/{name} is missing. Restore it from the repository.")
    for folder, _, files in os.walk(data_dir):
        for name in sorted(files):
            if not name.endswith(".json") or name in LOCAL_ONLY:
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, os.path.join(data_dir, "..")).replace(os.sep, "/")
            try:
                with open(path, encoding="utf-8") as f:
                    json.load(f)
            except (OSError, ValueError) as exc:
                problems.append(f"{rel} could not be read as JSON ({type(exc).__name__}). Restore it from the repository.")
    try:  # the guide's own validation: every text the explanation cards need
        strategy_guide.load(os.path.join(data_dir, "strategy_guide.json"))
    except OSError:
        pass  # a missing or unreadable file is reported above
    except ValueError as exc:
        if "is missing" in str(exc):  # JSON errors are reported above; this is valid JSON with a text missing
            problems.append(f"data/strategy_guide.json: {exc}")
    if os.path.normcase(os.path.abspath(data_dir)) == os.path.normcase(os.path.abspath(DATA_DIR)):
        for scenario in paper_market.scenario_ids():
            try:
                paper_market.get(scenario)
            except Exception as exc:  # noqa: BLE001 - any failure to load a practice market blocks the release
                problems.append(f"Practice market {scenario} could not be loaded ({type(exc).__name__}).")
    if not config.PAPER_STATE_SECRET:
        key = config.PAPER_KEY_PATH
        if os.path.exists(key):
            if os.path.getsize(key) == 0:
                problems.append(f"The practice-session key file {key} is empty. Delete it to have a new one created.")
        elif not os.access(os.path.dirname(os.path.abspath(key)) or ".", os.W_OK):
            problems.append(f"No PAPER_STATE_SECRET is set and the key folder for {key} cannot be written, so practice "
                            "sessions could not be signed.")
    return problems


def is_loopback(host):
    return host in ("127.0.0.1", "localhost", "::1")
