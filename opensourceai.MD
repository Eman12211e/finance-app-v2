# opensourceai.MD

Finance App V2: a beginner-friendly financial education app (Flask + vanilla JS). It is an overhaul of V1, not a
rebuild. Repository: https://github.com/Eman12211e/finance-app-v2 (remote `origin`).

V1 (https://github.com/Eman12211e/beginner-friendly-finance-app) is a read-only reference. Never modify it.

## Branches

- `main`: the V1 baseline import (`Import V1 at 2eb7701`). Changes reach it only by a merge the owner approves.
- `dev/v2`: the active development branch. All V2 work happens here.

## How to work here

- Simple architecture: fewest files and layers that work. No abstractions "for later".
- Minimal dependencies: standard library and platform features first. Ask before adding any dependency.
- Secure coding: validate all user input, never commit secrets (use env vars, keep `.env` out of git), treat money
  values carefully (integer cents or `Decimal`, not floats).
- Never request, store or log Social Security numbers, identity documents, passwords or other account-opening data.
- Incremental testing: each non-trivial change ships with a small test; run tests before committing.
- Build in small steps; one feature per commit.

## Zero-cost development

- `ZERO_COST_MODE` stays on (the default) unless the owner approves turning it off. While on, no paid or metered call
  is possible: keys are ignored, market data is demo data, and every AI call site refuses before creating a client.
- No real AI inference (paid or free credits), no paid data requests, no model-weight downloads without approval.
- Tests never make network or AI calls: `tests/conftest.py` blocks them. Live paths are tested with fakes.
- Simulated (mock) model output is always labelled `SIMULATED — NOT REAL MODEL OUTPUT` and never presented as a
  score, ranking, benchmark or investment result.

## Git rules

- Commits use the owner's (Eman's) configured Git identity, with no AI co-author or attribution lines.
- Local commits on `dev/v2` are allowed for approved milestones.
- Ask before: pushing, force-pushing, merging, tagging, deleting files, installing dependencies.
