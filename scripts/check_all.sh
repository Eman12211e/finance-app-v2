#!/usr/bin/env bash
# Every automated check, from scratch: a fresh virtual environment from requirements-dev.lock (must install exactly the
# locked versions), pytest in zero-cost mode (no network, no keys), then each browser suite on its own (they start the
# app on 127.0.0.1 and a headless browser). Exits non-zero if anything fails. CI runs this same script.
# Usage: bash scripts/check_all.sh [output-dir]      env: CHECK_SUITES (default: all), BROWSER (Edge or Chrome path)
set -u
cd "$(dirname "$0")/.."
OUT="${1:-check-all-out}"
SUITES="${CHECK_SUITES:-workflows overlays panes explanations drawings backtest visual_audit}"
mkdir -p "$OUT"
status=0
fail() { echo "FAIL: $1"; status=1; }

if command -v python3.12 >/dev/null 2>&1; then PY=(python3.12); elif command -v py >/dev/null 2>&1; then PY=(py -3.12); else PY=(python3); fi
VENV="$(mktemp -d)/venv"  # short temporary path: one locked package has very long file names (Windows path limit)
"${PY[@]}" -m venv "$VENV" || { echo "FAIL: could not create a Python 3.12 virtual environment"; exit 2; }
VPY="$VENV/bin/python"; [ -x "$VPY" ] || VPY="$VENV/Scripts/python.exe"
"$VPY" -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version" || { echo "FAIL: Python 3.12 is required"; exit 2; }
"$VPY" -m pip install --disable-pip-version-check -q -r requirements-dev.lock > "$OUT/install.txt" 2>&1 || { echo "FAIL: install (see $OUT/install.txt)"; exit 2; }
"$VPY" -m pip check > "$OUT/pip_check.txt" 2>&1 || fail "pip check"
"$VPY" -m pip freeze --all --exclude pip > "$OUT/freeze.txt"
diff --strip-trailing-cr <(grep -v '^#' requirements-dev.lock) "$OUT/freeze.txt" > "$OUT/lock_diff.txt" || fail "installed packages differ from requirements-dev.lock"

git status --porcelain > "$OUT/git_status_before.txt"
ZERO_COST_MODE=1 "$VPY" -m pytest -q -p no:cacheprovider > "$OUT/pytest.txt" 2>&1 || fail "pytest"
echo "pytest: $(tail -1 "$OUT/pytest.txt")"
for suite in $SUITES; do
  PYTHON="$VPY" node scripts/qa/run.mjs "$OUT/qa-$suite" "$suite" || fail "browser suite $suite"
done
git status --porcelain > "$OUT/git_status_after.txt"
diff "$OUT/git_status_before.txt" "$OUT/git_status_after.txt" > /dev/null || fail "the checks changed tracked files"

"$VPY" --version > "$OUT/python_version.txt" 2>&1
echo "check_all: $([ "$status" = 0 ] && echo PASSED || echo FAILED) (logs in $OUT)"
exit "$status"
