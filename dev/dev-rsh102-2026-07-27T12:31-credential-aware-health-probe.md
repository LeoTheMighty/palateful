---
hash: rsh102
type: dev
created: 2026-07-27T12:31:00-06:00
title: Credential-aware health probe — fresh connection, fail-open classifier
from: plan/plan-462355-2026-07-27T10:51-rotation-self-heal.md
status: ready
owner: null
branch: feat/dev-rsh102
---

## Goal

Replace the pooled-connection, bare-`except` health probe with a
**fresh**-connection probe that returns 503 **only** on a positively-
identified auth failure. Today `health_router.py:15-28` probes a pooled
connection via `Depends(get_async_database)` — pooled connections stay
authenticated across a rotation, so it structurally cannot see one — and
catches bare `Exception` → 503, which is a mass-task-replacement hazard.

This phase also carries the **first `terraform apply` since 2026-04-26** and
the first real exercise of the deploy lane. It is doing three risky things at
once; the ACs reflect that.

**Deadline: 2026-07-29.**

## Acceptance criteria

- [ ] **Before merging**: `terraform plan` run locally against
      `terraform/environments/prod`, full pending diff reviewed line by line
      and pasted into this status log, with
      `aws_secretsmanager_secret_rotation.db_master` explicitly called out.
      This is the only review gate before an unattended `-auto-approve`
      (`ci.yml:748`) applies everything pending since 2026-04-26.
- [ ] `libraries/utils/utils/services/db_credentials.py` exists with
      `is_auth_error(exc) -> bool` matching `exc` → `.orig` → `__cause__`,
      on SQLSTATE/`pgcode` **or** message pattern (`password authentication
      failed`, `no password supplied`).
- [ ] `is_auth_error` classifies a **live** psycopg2 *and* asyncpg
      connect-time auth failure correctly (docker-compose Postgres, wrong
      password) — not only a constructed exception.
- [ ] `libraries/utils/utils/services/db_probe.py` exists with `ProbeVerdict`,
      `probe_async`, `probe_sync`, single-flight `cached_verdict_async`,
      `_reset_verdict_cache()`, `_now()` clock seam, `_connect_once()` connect
      seam, `_probe_url()`, a `__main__` CLI, and `poolclass=NullPool`.
- [ ] Unset probe URL classifies **OK** (nothing to authenticate against).
- [ ] `health_check` reads the cached verdict and **no longer declares the
      `get_async_database` dependency**. 503 body is
      `{"detail": "db credentials invalid", "db": "AUTH_FAILED"}`; 200 body is
      `{"status": "ok", "db": "<verdict>"}`.
- [ ] 503 for **both** `28P01` and `28000` raised at the patched connect seam
      (E-2). 200 for a timeout, an `OperationalError` without an auth
      SQLSTATE, a DNS failure, **and** a bare `RuntimeError` (E-3).
- [ ] E-4: at most 1 fresh connection per 60s window. Both cases pass — a
      rapid burst of N probes, **and** an interleaved 30s/60s schedule
      crossing a TTL boundary. The latter passes only if the cache is
      single-flight, so it is the case that actually tests the design.
- [ ] Autouse cache-reset fixture promoted from `test_health.py` into
      `services/api/tests/conftest.py` (T2.6) so `test_main.py`,
      `test_async_client_fixture.py` and the `conftest.py` example stay
      order-independent.
- [ ] `DB_PROBE_TTL_S` configurable, default 60.
- [ ] Coverage assertion over `coverage/libraries/utils/coverage.xml` for
      `db_credentials.py` and `db_probe.py` (T2.8) — `libraries/utils` sets no
      `fail_under`, so the highest-risk new code otherwise lands where nothing
      enforces coverage.
- [ ] `npx nx run api:test` passes with coverage still at 100%.
- [ ] **On the `main` push**: `deploy-images` runs all four legs,
      `run-migrator` succeeds, `terraform-prod` succeeds, and
      `deploy-services` reaches conclusion `success` — closing E-1's second
      half.
- [ ] `deploy-images (parser)` outcome recorded. If the 2026-05-03 failure
      reproduces, pin the unpinned fetches in `services/parser/Dockerfile.batch`
      **inside this story** — it blocks every remaining phase.
- [ ] The rotation-cadence resource is confirmed applied and the new
      next-rotation date recorded in the status log.

## Technical notes

- **`is_auth_error` must match the raw DBAPI error, not only `.orig`.** In
  rsh105's `do_connect` listener the exception from `dialect.connect(...)` is
  the **unwrapped** DBAPI error — SQLAlchemy wraps only above the pool
  creator. psycopg2 connect-time `OperationalError`s come from libpq without
  a `PGresult`, so `.pgcode` is commonly `None`.
- **The verdict cache is process-global.** `conftest.py:1485`,
  `test_main.py:46` and `test_async_client_fixture.py:15` all hit
  `/v1/health`; a leaked `AUTH_FAILED` verdict makes them order-dependent.
- **`test_health_check_db_failure` inverts.** It asserted a `RuntimeError`
  produces `503 {"detail": "db unavailable"}`; under FR-2's fail-open rule an
  unclassified exception returns **200**. Deliberate behaviour change — call
  it out in the PR body and the tour's decision ledger.
- **The api test suite requires `DATABASE_URL` in the environment.**
  `conftest.py:15` does `setdefault("DATABASE_URL", "")` and
  `config.Settings` rejects the empty string, so a bare local run errors at
  fixture setup with a pydantic `ValidationError`. CI sets it at
  `ci.yml:176`/`:260`; do the same locally
  (`DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test`).
  Corrects plan.md:341-347, which reads as though `""` is the working state.
- **`services/api` enforces `fail_under = 100`** (`pyproject.toml:43`), so a
  *single-file* api pytest run always exits non-zero on coverage alone. Judge
  test outcomes from the report, not the exit code, when running one file.
- `libraries/utils` tests live in `libraries/utils/test/` (singular, no
  `conftest.py`); its `pyproject.toml:9-11` supplies its own
  `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, and **that**
  config wins — the root config never applies. Neither psycopg2 nor asyncpg
  is pinned there, which is why the live-driver classification leg (T2.3)
  runs against docker-compose rather than in the unit suite.
- `poolclass=NullPool` is the point, not an optimization — every probe must
  be a genuinely new connection and TLS handshake.
- **Accepted risk, stated explicitly.** Both services set
  `deployment_minimum_healthy_percent = 0` (`ecs/main.tf:371`, `:473`) and the
  ALB matches only `200` with `unhealthy_threshold = 3` at 60s
  (`alb/main.tf:58-71`). A real rotation makes every task's probe fail at
  once. That **is** the intended self-heal; the fail-open classifier is what
  keeps it from firing on a transient blip. The API-unavailable window during
  a genuine rotation is bounded only by task replacement time and is not
  measured until rsh109.
- **`run-migrator` is the next unproven link** — it gates `deploy-services`
  (`ci.yml:850`) and `services/migrator` implicitly depends on `utils`, so
  touching `libraries/utils` runs it for the first time since 2026-04-26.
- No Terraform change is needed for detection: the container health check
  (`ecs/main.tf:318-324`) and the ALB target group already turn a 503 into a
  task replacement.
- RED artifacts (do **not** re-author, only make green):
  `services/api/tests/test_health.py` (E-2, E-3, E-4).
- Full context: `_devx/workstreams/rotation-self-heal/plan.md` §Phase 2.

## Status log

- 2026-07-27T12:31 — emitted from plan 462355 at RED-gate PASS. E-2/E-3/E-4
  observed RED right-reason (`ModuleNotFoundError: utils.services.db_probe`,
  plus `test_health_check` failing on the new `db` body field); see
  `_devx/workstreams/rotation-self-heal/evals/RED-report.md`.
