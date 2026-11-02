"""P6 step 1: the requirement files and their locks agree. Every top-level pin is in the locks at the same version,
every lock line is an exact pin, and the development lock is the runtime lock plus the test tools."""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")


def pins(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        lines = [l.split("#")[0].strip() for l in f]
    return [l for l in lines if l and not l.startswith("-r")]


def as_dict(lines):
    return {l.split("==")[0].lower().replace("_", "-"): l.split("==")[1] for l in lines}


def test_every_line_is_an_exact_pin():
    for name in ("requirements.txt", "requirements-dev.txt", "requirements-build.txt", "requirements.lock",
                 "requirements-dev.lock"):
        for line in pins(name):
            assert re.fullmatch(r"[A-Za-z0-9_.\-]+==[A-Za-z0-9_.\-+]+", line), (name, line)


def test_the_locks_hold_the_top_level_pins_and_the_dev_lock_extends_the_runtime_lock():
    runtime, dev = as_dict(pins("requirements.lock")), as_dict(pins("requirements-dev.lock"))
    for name, version in as_dict(pins("requirements.txt")).items():
        assert runtime[name] == version and dev[name] == version, name
    assert dev["pytest"] == as_dict(pins("requirements-dev.txt"))["pytest"]
    assert all(dev[name] == version for name, version in runtime.items())  # same versions where they overlap
    assert "pytest" not in runtime and "yfinance" not in dev  # tests and the data-build tool stay out of the runtime


def test_python_version_is_declared():
    with open(os.path.join(ROOT, ".python-version"), encoding="utf-8") as f:
        assert f.read().strip() == "3.12"
