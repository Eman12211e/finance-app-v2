# P6 progress log — Release preparation

Read this first after any context reset. Brief and roadmap: `docs/P6_BRIEF.md`. Findings: `docs/P6_RELEASE_AUDIT.md`.
Base: `dev/v2` at `c335175` (P5 accepted 2026-11-02, including the step 9 content addendum).

| Commit | Step |
|---|---|
| this commit | 0: release-readiness audit, brief and roadmap (for owner review) |

## Resolve before next step

Carried forward from review. Each item must be closed (done, decided or explicitly accepted by the owner) before the
named step starts. Add new items from every review here; do not delete closed ones, mark them closed with the commit
or decision.

| # | Item | Needed before | Status |
|---|---|---|---|
| 1 | Owner approves the audit (`P6_RELEASE_AUDIT.md`) and the roadmap (`P6_BRIEF.md`) | Step 1 | Open |
| 2 | Owner approves network access to PyPI to install the pinned packages into this repository's own venv (installing dependencies) | Step 1 | Open |
| 3 | Owner confirms that the release target is a **controlled, local** release (own computers, or one machine on a private network), not a hosted public launch. This sets the scope of F2, R3 and Step 4 | Step 3 | Open |
| 4 | Owner approves Waitress as a new runtime dependency (or names an alternative) | Step 3 | Open |
| 5 | Owner decides on CI: (a) authorize adding `.github/workflows/ci.yml` and, separately, a push so it runs; or (b) local `check_all` only, with "not independent" stated in every report | Step 2 gate | Open |
| 6 | Owner decides the project licence | Step 5 | Open |
| 7 | Owner decides the Explore tab's Yahoo-derived `demo_stocks.json`: replace with synthetic, keep with attribution and a "not current" label, or remove | Step 5 | Open |
| 8 | Owner sets a review-date policy for brokerage and tax facts (for example "older than 12 months is flagged") | Step 5 | Open |
| 9 | Owner names who performs the manual screen-reader and real-phone checklist, or accepts deferring it as a known limitation | Step 6 gate | Open |
| 10 | Optional: owner provides the roadmap v3 document, so it can be committed and checked against | Step 7 | Open |

## Step 0 — Release-readiness audit and plan

- Read the README, `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `config.py`, `app.py`, the requirements, the
  `.gitignore` and tracked files, the P5 evidence and the routes' error and logging code. Probed the app with Flask's
  test client, using the V1 virtual environment that produced every earlier total.
- Findings (`P6_RELEASE_AUDIT.md`):
  - Critical: none.
  - High: F1 (no clean install or independent test run), F2 (development server only), R1 (licence and data
    provenance).
  - Medium: F3 (dependency pinning), F4 (security headers), F5 (HTML 404 / 405 under `/api/`), F6 (startup
    diagnostics, demonstrated with `LAB_MAX_TOKENS=abc`); R2 (accessibility outside P5), R3 (load on a shared host),
    R4 (dated third-party facts).
  - Low: F7–F10, R5; improvements I1–I4.
- Roadmap: eight numbered steps after this one. Release blockers come first: environment, CI, runtime, security,
  licensing. Cosmetic work comes last.
- No code, configuration or dependency was changed. Only these three documents were added.
- **Self-audit only.** Nothing in Step 0 is independent verification. The reported P5 totals (993 pytest, 480 browser
  checks) remain the implementer's own until Step 2.
