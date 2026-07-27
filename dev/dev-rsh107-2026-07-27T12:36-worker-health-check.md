---
hash: rsh107
type: dev
created: 2026-07-27T12:36:00-06:00
title: Worker health check — remove healthStatus UNKNOWN without a crash loop
from: plan/plan-462355-2026-07-27T10:51-rotation-self-heal.md
status: ready
owner: null
branch: feat/dev-rsh107
---

## Goal

Give the worker a health-check mechanism where it has none
(`terraform/modules/ecs/main.tf:396-444` defines no `healthCheck` block, so
ECS reports `healthStatus: UNKNOWN`). Not on the outage path — FR-5 already
removes the credential failure — but it removes `UNKNOWN`, which is what E-8
measures.

## Acceptance criteria

- [ ] `db_probe`'s `__main__` CLI is hardened: top-level `BaseException`
      catch → **exit 0**; exit 1 **only** on a positively-classified
      `AUTH_FAILED`.
- [ ] A test asserts the CLI exits 0 when the DB driver is unavailable and
      when the module raises at import.
- [ ] The deployed worker image tag is verified **≥ the rsh102 merge SHA**
      (`aws ecs describe-task-definition --task-definition
      palateful-worker-prod`) before applying — otherwise `db_probe` is not in
      the running image.
- [ ] `healthCheck` block added to the worker container definition with
      `CMD-SHELL` invoking `python -m utils.services.db_probe`,
      `interval = 60`, and a `startPeriod` tuned to observed Celery boot time.
- [ ] **0** worker tasks report `healthStatus: UNKNOWN`; the worker reports
      `HEALTHY` within **120s** of task start.
- [ ] **Fail-open against self-failure**: renaming/breaking the probe module,
      or removing its DB driver, leaves the task `HEALTHY` — it must never
      crash-loop because the probe could not run.
- [ ] A simulated non-auth DB error does **not** mark the task unhealthy.
- [ ] A genuine `AUTH_FAILED` **does** — run this leg with
      `DB_PASSWORD_SECRET_ARN` temporarily unset on the worker, and state the
      rollback (re-set the variable, force a deployment) before starting.
- [ ] **E-4 on the worker path**: measured connects/hour **≤ 60** and
      `get_secret_value`/hour **≤ 60** per task.
- [ ] Actuals recorded in
      `_devx/workstreams/rotation-self-heal/evals/E-8_worker-healthcheck.md`.

## Technical notes

- **The CLI must be fail-open against its own failure to start.**
  `python -m utils.services.db_probe` exits non-zero on *any* startup problem —
  ImportError, missing driver, PATH issue — not only `AUTH_FAILED`. Concrete,
  not hypothetical: `libraries/utils/pyproject.toml` declares **neither**
  psycopg2 nor asyncpg (only `services/worker/pyproject.toml:11,18` do), and
  the worker image sets `WORKDIR`/`PYTHONPATH` to `$DOCKER_SERVICE_ROOT/src`
  (`services/worker/Dockerfile:131,133`). Combined with
  `deployment_minimum_healthy_percent = 0` (`ecs/main.tf:473`) and no ALB, a
  probe that cannot start becomes an unbounded crash loop — re-introducing on
  the worker the mass-replacement hazard FR-2 removes from the API.
- **Why `interval` is 60s, not 30s.** Each `CMD-SHELL` invocation is a cold
  process, so the in-process TTL cache that bounds E-4 on the API path cannot
  apply: at 30s that would be one real connect — and, post-FR-5, one
  `get_secret_value` — per check, ~2,880 SM calls/day/task, which **exceeds
  E-4's threshold**. Pinning 60s satisfies "at most 1 fresh connection per
  60s" by construction and avoids inventing an on-disk cache. The cost is
  coarser detection granularity on the worker, which is acceptable.
- **This story is terraform-plus-`libraries/`**: the CLI hardening triggers the
  deploy lane, but the `healthCheck` block applies via Force Deploy if it
  lands in a terraform-only commit.
- Adding fastapi/uvicorn to a Celery-only image to serve one route is a
  heavier change than the CLI — hence `CMD-SHELL`.
- **Be precise about what this buys.** It establishes the mechanism and
  removes `UNKNOWN`. It does **not** make worker liveness observable in
  general: a Celery consumer wedged on a poisoned task still holds valid
  credentials and still reports `HEALTHY`. Named in the plan's "NOT doing".
- Verification type: human. RED artifact (stub, deferred):
  `_devx/workstreams/rotation-self-heal/evals/E-8_worker-healthcheck.md` (E-8,
  P1) — the observation protocol is pre-written; this story fills in actuals.
- Full context: `_devx/workstreams/rotation-self-heal/plan.md` §Phase 7.

## Status log

- 2026-07-27T12:36 — emitted from plan 462355 at RED-gate PASS. E-8 is a
  deferred human stub (legal for P1); the eval file carries the full
  observation protocol and pass conditions.
