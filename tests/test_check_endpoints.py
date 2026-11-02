"""scripts/check_endpoints.py (P6 step 1, finding F7): a run that checks nothing (no keys, or zero-cost mode) must leave
data/endpoint_check.json alone. Live mode reads that file to skip failed provider endpoints, so overwriting it with
SKIP rows would discard the last real result and leave the working tree dirty. Offline: no request is made."""
import importlib.util
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_script():
    spec = importlib.util.spec_from_file_location("check_endpoints", os.path.join(ROOT, "scripts", "check_endpoints.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_run_without_keys_leaves_the_last_real_result_unchanged(tmp_path, monkeypatch, capsys):
    script = load_script()
    out = tmp_path / "endpoint_check.json"
    out.write_text('{"checked_at": "2026-10-24T22:41:29Z", "results": []}', encoding="utf-8")
    monkeypatch.setattr(script, "OUT_PATH", str(out))
    script.main()  # conftest blanks every key, so each endpoint is a SKIP and no request is made
    assert out.read_text(encoding="utf-8") == '{"checked_at": "2026-10-24T22:41:29Z", "results": []}'
    printed = capsys.readouterr().out
    assert sum(line.startswith("SKIP ") for line in printed.splitlines()) == len(script.endpoints())
    assert "left unchanged" in printed
