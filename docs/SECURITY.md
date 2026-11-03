# Security notes and threat model (P6 step 4)

Scope: the **controlled local release**. The app runs on the user's own computer, or on one machine in a private
network the owner trusts. `serve.py` listens on `127.0.0.1` unless `HOST` is set, and says so loudly when it is. It
has no accounts, no login, no stored personal data, no real money and no real orders. In zero-cost mode (the default)
it makes no outbound request at all.

## What is protected, and how

| Asset or threat | Control | Verified by |
|---|---|---|
| Practice sessions being forged (changing balances, peeking at future days) | The session lives in the browser, signed with HMAC-SHA256. The key is `PAPER_STATE_SECRET` or a local key file (gitignored, created atomically), compared in constant time. A tampered state answers `INVALID_STATE`, and the server re-checks that a correctly signed state is well formed | `tests/test_paper_engine.py`, P4 and P5 tampering tests, `tests/test_security.py` |
| Future prices reaching the page | Every price reply goes through `paper_engine.market_bars(state)` and stops at the session's day | P4 and P5 no-look-ahead tests |
| Script injection (XSS) | The frontend builds the page from text nodes only (no `innerHTML`, `document.write`, `eval` or `new Function`); Jinja autoescapes; a strict CSP (`default-src 'self'`, no inline script or style, no remote origin) is the second line | `tests/test_security.py` (a sweep of every script, the template check, the CSP) and every browser suite under the CSP |
| Clickjacking | `frame-ancestors 'none'` and `X-Frame-Options: DENY` | `tests/test_security.py` |
| MIME confusion; referrer leaks on outbound links | `X-Content-Type-Options: nosniff`; `Referrer-Policy: no-referrer` | `tests/test_security.py` |
| Oversized or malformed requests | A 64 KB limit checked **before any route runs** (JSON 413); every endpoint validates exact fields and types; seeded fuzz tests (P4, P5) | `tests/test_security.py`; endpoint tests |
| Internal details in errors | Route errors and Flask's own 404 / 405 / 500 under `/api/` all answer in the JSON envelope with a plain message. Tracebacks go to the server log only. The release server sends no `Server` header | `tests/test_security.py`, `tests/test_startup.py` |
| Secrets in logs or replies | Keys are blanked in zero-cost mode; `/api/health` says only whether a key exists; no route logs request bodies, sessions or signatures; user-supplied values in logs are quoted with `repr()` (no forged log lines) | `tests/test_security.py` |
| Paid or metered calls | `ZERO_COST_MODE` is on unless explicitly `0`; tests block all network and AI calls | `tests/conftest.py`, `tests/test_startup.py` |
| Exposure on a network | Loopback by default; any other `HOST` is announced at start | `tests/test_startup.py` |

## Accepted risks (owner to confirm)

- **R5, session replay:** a user can restore an older, validly signed copy of their own practice session (for example
  to undo a trade). It affects only their own fictional practice, and no other user or real money.
- **R3, request volume:** there is no rate limit. In the local model the only client is the user. Waitress handles at
  most `THREADS` requests at once (default 4), and a strategy test costs about 25 ms. If the app is ever opened to a
  network (`HOST`), anyone who can reach it can use it; there is no login. That is a deployment decision outside this
  release.
- **No HTTPS:** not needed on loopback. A network deployment would need a reverse proxy with TLS, which is out of
  scope.
- **Dependencies:** pinned in the lock files; no automated vulnerability scan yet (P6 audit I1, optional and needing
  approval).
