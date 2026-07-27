# E-8 — Worker liveness is observable

- **Priority:** P1 · **Validation type:** human · **Phase:** 7 (FR-3)
- **Status:** RED — stub. No observation recorded yet.

## Expectation

When the worker task is running, the system SHALL report a health status
other than `UNKNOWN`, so ECS can detect and replace a broken worker.

**Threshold:** 0 worker tasks report `healthStatus: UNKNOWN`; the worker
reports `HEALTHY` within 120s of task start.

## Baseline (pre-change)

`terraform/modules/ecs/main.tf:396-444` defines the worker container with no
`healthCheck` block, so ECS reports `healthStatus: UNKNOWN` for every task.
The image has no HTTP surface (Celery only), which is why the probe is a
`CMD-SHELL` invocation of `python -m utils.services.db_probe` rather than a
route.

## Observation protocol

| # | Step | Expected | Actual |
|---|---|---|---|
| 1 | `aws ecs describe-tasks` after the deployment | **0** tasks report `UNKNOWN` | _pending_ |
| 2 | Time from task start to first `HEALTHY` | **< 120s** | _pending_ |
| 3 | Break the probe (rename the module / remove its DB driver) | task stays `HEALTHY`, no crash loop | _pending_ |
| 4 | Simulate a non-auth DB error | task **not** marked unhealthy | _pending_ |
| 5 | Genuine `AUTH_FAILED`, with `DB_PASSWORD_SECRET_ARN` unset on the worker | task **is** marked unhealthy and replaced | _pending_ |
| 6 | Measured connects/hour per task | **≤ 60** | _pending_ |
| 7 | Measured `get_secret_value`/hour per task | **≤ 60** | _pending_ |

**Step 3 is the one that can take production down.** `python -m
utils.services.db_probe` exits non-zero on *any* startup problem, not only
`AUTH_FAILED` — and this is concrete, not hypothetical:
`libraries/utils/pyproject.toml` declares neither psycopg2 nor asyncpg (only
`services/worker/pyproject.toml:11,18` do), and the worker image sets
`WORKDIR`/`PYTHONPATH` to `$DOCKER_SERVICE_ROOT/src`
(`services/worker/Dockerfile:131,133`). Combined with
`deployment_minimum_healthy_percent = 0` (`ecs/main.tf:473`) and no ALB, a
probe that cannot start becomes an unbounded crash loop — re-introducing on
the worker the exact mass-replacement hazard FR-2 removes from the API.
Contract: catch `BaseException` at the top level, **including import
failure**, and exit 0. Exit 1 only on a positively-classified `AUTH_FAILED`.

**Step 5 needs the variable unset first.** Once FR-5 is enabled, the provider
heals the break within its 300s TTL and the true-positive leg silently passes
for the wrong reason. State the rollback (re-set `DB_PASSWORD_SECRET_ARN`,
force a deployment) **before** starting.

**Steps 6–7 are E-4 on the worker path.** Each `CMD-SHELL` invocation is a
cold process, so the in-process TTL cache that bounds the API path cannot
apply. At a 30s interval that would be ~2,880 Secrets Manager calls/day/task,
which exceeds E-4's threshold. Resolved by pinning `healthCheck.interval = 60`
— satisfying "at most 1 fresh connection per 60s" by construction rather than
inventing an on-disk cache.

## Precondition

The deployed worker image tag must be **≥ the Phase 2 merge SHA**, or
`db_probe` is not in the running image and step 1 fails for a reason that has
nothing to do with FR-3. Verify with
`aws ecs describe-task-definition --task-definition palateful-worker-prod`
before applying (T7.3).

## What this does NOT buy

It establishes the mechanism and removes `UNKNOWN`. It does **not** make
worker liveness observable in general: a Celery consumer wedged on a poisoned
task still holds valid credentials and still reports `HEALTHY`. Named in the
plan's "NOT doing".

## Result

- **Verdict:** _pending_
- **Time to first `HEALTHY`:** _pending_
- **Date observed:** _pending_

## Links

- Plan phase 7: `../plan.md`
- Expectation: `../expectations.md` (E-8)
