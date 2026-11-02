# QA fixtures

`skipped_entries.json` is a `/api/backtest/run` reply for made-up prices above $10,000 a share (no synthetic ticker
reaches that), so the browser suite can show skipped entries. It is the real route's own output with only the market
bars replaced; `tests/test_backtest_api.py::test_the_skipped_entry_fixture_is_the_servers_own_reply` rebuilds it and
fails if this file differs. To regenerate after an intended change, write `skipped_entry_reply()` from that test module
to this file as compact JSON.
