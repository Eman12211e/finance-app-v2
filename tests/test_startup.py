"""P6 step 3: settings validation (finding F6), the release start-up check and `serve.py` (finding F2): local by
default, plain-language failures with a non-zero exit, a `--check` mode that starts and writes nothing, and a real
start and stop on 127.0.0.1. Subprocesses get their own environment, so the test process's settings never change."""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from services import startup

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_ENV = {k: v for k, v in os.environ.items() if not k.startswith(("LAB_", "HOST", "PORT", "THREADS", "DATA_MODE"))}


def run(args, **env):
    """Runs python with the given arguments in the repository, with the test environment plus `env`."""
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=BASE_ENV | env, capture_output=True, text=True,
                          timeout=60)


def settings(**env):
    out = run(["-c", "import config, json; print(json.dumps({'problems': config.PROBLEMS, 'tokens': config.LAB_MAX_TOKENS,"
                     " 'timeout': config.LAB_TIMEOUT_SECONDS, 'host': config.HOST, 'port': config.PORT,"
                     " 'threads': config.THREADS, 'zero': config.ZERO_COST_MODE}))"], **env)
    assert out.returncode == 0, out.stderr  # a bad value never stops the import
    return json.loads(out.stdout.strip().splitlines()[-1])


# ---- settings ----

def test_defaults_are_valid_local_and_zero_cost():
    s = settings()
    assert s["problems"] == [] and (s["host"], s["port"], s["threads"]) == ("127.0.0.1", 5000, 4) and s["zero"] is True


@pytest.mark.parametrize("name, value, phrase", [
    ("LAB_MAX_TOKENS", "abc", "LAB_MAX_TOKENS must be a whole number from 1 to 100000"),
    ("LAB_TIMEOUT_SECONDS", "-5", "LAB_TIMEOUT_SECONDS must be a whole number from 1 to 600"),
    ("PORT", "99999", "PORT must be a whole number from 1 to 65535"),
    ("THREADS", "0", "THREADS must be a whole number from 1 to 64"),
    ("DATA_MODE", "real", "DATA_MODE must be demo or live"),
    ("ZERO_COST_MODE", "maybe", "ZERO_COST_MODE must be 0 or 1"),
    ("LAB_DAILY_BUDGET_USD", "lots", "LAB_DAILY_BUDGET_USD must be an amount of dollars, 0 or more"),
    ("WARM_CACHE", "yes", "WARM_CACHE must be 0 or 1"),
    ("HOST", "", "HOST must not be empty")])
def test_an_invalid_setting_is_reported_in_plain_words_not_a_traceback(name, value, phrase):
    s = settings(**{name: value})
    assert any(phrase in p and repr(value) in p for p in s["problems"]), s["problems"]


def test_an_unclear_zero_cost_value_keeps_zero_cost_mode_on():
    assert settings(ZERO_COST_MODE="maybe")["zero"] is True  # only an explicit 0 turns it off


# ---- the start-up check ----

def test_the_repository_as_committed_is_ready():
    assert startup.check() == []


def copy_data(tmp_path):
    target = tmp_path / "data"
    shutil.copytree(os.path.join(ROOT, "data"), target, ignore=shutil.ignore_patterns("paper_state.key", "lab_spend.json"))
    return target


def test_a_damaged_data_file_is_named(tmp_path):
    data = copy_data(tmp_path)
    (data / "brokerages" / "schwab.json").write_text("{ broken", encoding="utf-8")
    assert any("data/brokerages/schwab.json could not be read as JSON" in p for p in startup.check(str(data)))


def test_a_guide_missing_text_is_named(tmp_path):
    data = copy_data(tmp_path)
    guide = json.loads((data / "strategy_guide.json").read_text(encoding="utf-8"))
    del guide["footer"]
    (data / "strategy_guide.json").write_text(json.dumps(guide), encoding="utf-8")
    assert any("data/strategy_guide.json: The strategy guide is missing footer." in p for p in startup.check(str(data)))


@pytest.mark.parametrize("name", startup.REQUIRED)
def test_a_missing_required_file_is_named(tmp_path, name):
    data = copy_data(tmp_path)
    os.remove(data / name)
    assert f"data/{name} is missing. Restore it from the repository." in startup.check(str(data))


def test_an_empty_key_file_is_reported(tmp_path, monkeypatch):
    key = tmp_path / "paper_state.key"
    key.write_bytes(b"")
    monkeypatch.setattr(startup.config, "PAPER_STATE_SECRET", "")
    monkeypatch.setattr(startup.config, "PAPER_KEY_PATH", str(key))
    assert any("key file" in p and "is empty" in p for p in startup.check())


# ---- serve.py ----

def test_check_mode_reports_ready_and_starts_nothing():
    out = run(["serve.py", "--check"])
    assert out.returncode == 0 and "Ready: settings and data files are valid. It would serve http://127.0.0.1:5000 " \
        "(only on this computer)." in out.stdout


def test_check_mode_refuses_bad_settings_with_every_problem_listed():
    out = run(["serve.py", "--check"], PORT="abc", LAB_MAX_TOKENS="x")
    assert out.returncode == 1 and out.stderr.startswith("Finance App V2 cannot start:")
    assert "PORT must be a whole number" in out.stderr and "LAB_MAX_TOKENS must be a whole number" in out.stderr
    assert "Traceback" not in out.stderr


def test_a_network_host_is_named_as_such():
    out = run(["serve.py", "--check"], HOST="0.0.0.0")
    assert out.returncode == 0 and "ON THE NETWORK" in out.stdout


def test_unknown_arguments_show_the_usage():
    out = run(["serve.py", "--public"])
    assert out.returncode == 2 and "Usage: python serve.py [--check]" in out.stderr


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_serve_starts_on_loopback_answers_and_stops():
    port = free_port()
    proc = subprocess.Popen([sys.executable, "serve.py"], cwd=ROOT, env=BASE_ENV | {"PORT": str(port)},
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        body = None
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as resp:
                    body, server = json.load(resp), resp.headers.get("Server")
                break
            except OSError:
                time.sleep(0.1)
        assert body and body["ok"] and body["data"]["zero_cost_mode"] is True
        assert not server or "waitress" not in server.lower()  # the server does not announce itself
    finally:
        proc.terminate()
        out, err = proc.communicate(timeout=20)
    assert f"Finance App V2 on http://127.0.0.1:{port} (only on this computer)" in out, (out, err)


def test_a_port_in_use_is_explained():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        out = run(["serve.py"], PORT=str(busy.getsockname()[1]))
    assert out.returncode == 1 and "cannot listen on 127.0.0.1" in out.stderr and "Set PORT" in out.stderr
