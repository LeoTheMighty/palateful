---
gate: PASS
status_reason: 'Contract evals run the real channel against a throwaway Postgres; wrappers make a wrong-reason failure visible.'
reviewer: '/devx-plan design'
updated: 2026-11-24
waiver: { active: false, approver: null, reason: null }
---

# Decision — admin-request-intake — 2026-11-24

## Subject

How the P0 evals exercise the operator channel before any of it exists.

## Decision

- **Live Postgres, throwaway database per session**, built with
  `Base.metadata.create_all` after creating `vector` and `pg_trgm`
  (measured 0.56 s for 51 tables on the local `pgvector/pgvector:pg16`).
  The repo's script-test convention mocks SQL text, which cannot be written
  before the SQL exists.
- **The real `bin/prod-script`** runs end to end with `aws` replaced by a
  PATH shim that reproduces the ECS-exec stream (banner, CRLF, merged
  keepalive escapes).
- **Wrappers under `evals/`** call pytest with `-o addopts=""`, because a
  single-file run in `services/api` exits 1 on a green run
  (`fail_under = 100`; measured: 8 passed, exit 1). Without that, Gate 4's
  nonzero-exit check would read every eval as RED whatever it tested.
- **Wrong reasons are loud.** Errors, skips and collection failures exit 3
  with `EVAL-WRONG-REASON`; Gate 4 still counts that as nonzero, so the
  RED-report quotes must be read, and are.
- **The wrappers pin the sha256 of the pytest files and the harness** they
  run, so Gate 4's lock on the wrapper extends to the tests it runs.

## Rejected

- SQL-text mocks (pin the implementation, not the contract).
- Pointing Verified-by straight at the pytest files (vacuous RED through
  the coverage exit, and unlocked tests).
