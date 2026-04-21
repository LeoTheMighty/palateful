# Story pim-4b — DB pool defaults + ALB health check

**Status:** done
**Epic:** epic-perf-infra-and-measurement
**Depends on:** pim-2 (max_connections=80) **merged AND rebooted** (so
`SHOW max_connections` returns 80 in prod). pim-1 for before/after.

## Scope

Two config-only changes, bundled because they're both "tune a dial and
move on":

1. `DB_POOL_SIZE` default 10 → 20; `DB_MAX_OVERFLOW` default 20 → 40.
   Both env-overridable so local dev / docker-compose can stick with
   the smaller defaults if desired. Pool + overflow = 60; leaves 20
   connections reserved for beat/worker/migrator/`psql` within the
   `max_connections=80` ceiling.
2. ALB target-group health check `interval: 30 → 60`, `timeout: 5 → 3`.
   Halves health-check volume on the hot path. Hung-task detection
   still fires within 2 min; ECS circuit breaker still gates failed
   deploys.

## Implementation notes

- `libraries/utils/utils/constants.py`: defaults flipped with a
  provenance comment. The `int(os.environ.get(...))` pattern is
  unchanged, so existing env overrides continue to work (and raise
  `ValueError` at import time if given non-numeric junk — tested).
- `terraform/modules/alb/main.tf`: health check block updated; no
  structural change, just two numbers.
- **Gate discipline**: the commit message and QA walkthrough both
  call out that this story must not merge until `SHOW
  max_connections=80` is confirmed in prod. If pim-2's static
  reboot hasn't happened yet, deploy the pool side later — the ALB
  change is independent and can land any time.

## File list

- `libraries/utils/utils/constants.py` [MODIFY] — `DB_POOL_SIZE` +
  `DB_MAX_OVERFLOW` default bumps.
- `libraries/utils/test/test_db_pool_constants.py` [NEW] — env-
  override read path + default-value regression + invalid-input
  behavior.
- `terraform/modules/alb/main.tf` [MODIFY] — health-check interval
  + timeout.

## Acceptance criteria — coverage

- AC1 — **Gate**: `SHOW max_connections` returns target value
  (operator step, pre-merge).
- AC2 ✅ `DB_POOL_SIZE=20`, `DB_MAX_OVERFLOW=40` defaults;
  env-overridable.
- AC3 ✅ ALB target-group health check `interval=60, timeout=3`.
- AC4 — Post-apply: no health-check flap, no `too many connections`
  errors in CloudWatch Logs, ECS circuit-breaker still engages on
  deploy failure (operator smoke test).
- AC5 ✅ Unit test covers env-override read path (4 tests).

## Follow-ups

- pim-5 lands Redis + Auth0 JWKS caching (parallel; doesn't gate on
  this story).
- pim-6 audits legacy migrations for non-CONCURRENTLY indexes.
