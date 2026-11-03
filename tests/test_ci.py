"""P6 step 2: the CI workflow and the check_all scripts. CI must run the same checks a person runs locally, with no
secrets, keys, paid services or market data, read-only repository permissions, and a failing exit on any failure."""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def run_mjs_suites():
    return re.search(r"const SUITES = \[([^\]]*)\]", read("scripts", "qa", "run.mjs")).group(1).replace('"', "").replace(",", " ").split()


def test_the_workflow_runs_check_all_on_python_3_12_with_read_only_permissions_and_no_secrets():
    ci = read(".github", "workflows", "ci.yml")
    assert "run: bash scripts/check_all.sh ci-out" in ci
    assert 'python-version: "3.12"' in ci and 'node-version: "22"' in ci
    assert "permissions:\n  contents: read" in ci and "write" not in ci
    assert "secrets." not in ci and "API_KEY" not in ci and "TOKEN" not in ci
    assert 'ZERO_COST_MODE: "1"' in ci
    assert "if: always()" in ci and "path: ci-out/" in ci  # logs are kept even when a check fails
    assert "timeout-minutes:" in ci


def test_check_all_installs_the_lock_and_fails_on_any_failure():
    sh = read("scripts", "check_all.sh")
    assert "-r requirements-dev.lock" in sh and "pip check" in sh and "differ from requirements-dev.lock" in sh
    assert 'ZERO_COST_MODE=1 "$VPY" -m pytest' in sh
    assert 'exit "$status"' in sh and sh.count("|| fail ") >= 4
    assert "the checks changed tracked files" in sh
    default = re.search(r'SUITES="\$\{CHECK_SUITES:-([^}]*)\}"', sh).group(1).split()
    assert default == run_mjs_suites()  # every browser suite the runner knows, in its order


def test_the_powershell_twin_runs_the_same_checks():
    ps = read("scripts", "check_all.ps1")
    assert "-r requirements-dev.lock" in ps and "pip check" in ps and '$env:ZERO_COST_MODE = "1"' in ps
    default = re.search(r'else \{ ([^}]*) \}', ps).group(1).replace('"', "").replace(",", " ").split()
    assert default == run_mjs_suites()
    assert "exit $(if ($failed.Count) { 1 } else { 0 })" in ps


def test_check_output_folders_are_ignored():
    ignored = read(".gitignore").split()
    assert "check-all-out/" in ignored and "ci-out/" in ignored
