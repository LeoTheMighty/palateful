---
hash: rsh106
type: dev
created: 2026-07-27T12:35:00-06:00
title: Engine-site registration + task-role IAM — wire FR-5, ship disabled
from: plan/plan-462355-2026-07-27T10:51-rotation-self-heal.md
status: ready
owner: null
branch: feat/dev-rsh106
---

## Goal

Wire rsh105's helper into all five long-lived engine sites and grant the task
roles the permission they need. Ships **disabled** — `DB_PASSWORD_SECRET_ARN`
stays unset, so merging is a no-op until it is explicitly set on a task
definition. Enablement is worker-first, then API; rollback is unsetting one
variable.

## Acceptance criteria

- [ ] Registered at all three `database.py` sites: `:43` (sync `db_engine`),
      `:91` (`create_async_engine`, via `.sync_engine`), `:121`
      (`error_log_engine`).
- [ ] Registered at `libraries/agent/agent/runner.py:25` and
      `libraries/agent/agent/tasks.py:28`.
- [ ] Enumeration guard: AST-scan `libraries/utils/utils/` +
      `libraries/agent/agent/` for `create_engine`/`create_async_engine`,
      assert each is registered, exclude `libraries/test-helper` **by name
      with a written reason**, and ensure it executes under **both** the
      `utils` and `agent` nx `test` targets.
- [ ] **E-6's second clause, in E-6's own artifact** (T6.3b): with
      `DB_PASSWORD_SECRET_ARN` unset, **0** Secrets Manager clients are
      constructed and **0** `do_connect` listeners registered across the wired
      sites — asserted against the live engines for `database.py`, and at the
      source level for the two `libraries/agent` sites (see Technical notes
      for why).
- [ ] With `DB_PASSWORD_SECRET_ARN` unset: `npx nx run api:test` and
      `poetry run pytest libraries/utils/` produce the same pass counts and
      exit codes as before the change, and `docker compose up` reaches a
      healthy api container (CAP-6).
- [ ] `terraform/modules/iam/main.tf` grants `secretsmanager:GetSecretValue` on
      the db master secret to `ecs_api_task` (`:416`) and `ecs_worker_task`
      (`:519`), copying the shape of the execution-role policy at `:362-378`.
- [ ] `DB_PASSWORD_SECRET_ARN` plumbed into both container definitions from
      `var.db_master_secret_arn` (`ecs/main.tf` `:306` and `:426` regions).
- [ ] `terraform plan` shows only the two IAM policies and the two env vars.
- [ ] Merged with the variable **unset**; zero behavior change confirmed.
- [ ] Enabled on the **worker first** via Force Deploy: worker tasks reach
      `RUNNING`, no auth errors in `/ecs/palateful-worker-prod`, and
      `audit_errors.py --service worker` shows no new error types. Then the
      API: `GET /v1/health` returns 200 with `db: OK`.
- [ ] CAP-3 verified for the API: force one api task into `AUTH_FAILED` (with
      `DB_PASSWORD_SECRET_ARN` temporarily unset on it) and confirm ECS
      replaces it. Nothing else in the plan proves the API-replacement half of
      CAP-3.

## Technical notes

- **`libraries/agent` is the easy miss.** `runner.py:25` and `tasks.py:28`
  each call `create_engine(settings.database_url, pool_pre_ping=True)`
  independently of `utils/services/database.py`. A fix confined to
  `database.py` leaves the worker's agent tasks still failing after a
  rotation — the partial fix that would make the workstream look done while
  the outage recurs.
- **Correction to plan.md:735 (T6.3b), found at RED.** The plan says the
  clause is proven by importing `runner.py` and `tasks.py` "against the live
  engines". Neither half holds: `agent` is not installed in the
  `libraries/utils` venv (`importlib.util.find_spec("agent")` is `None`), and
  both modules build their engines **lazily** inside `_get_session_factory()`,
  so an import constructs zero engines to inspect. The RED artifact therefore
  proves the clause the only way it is provable from that runner: live-engine
  assertions over `database.py`'s three sites (reloaded against a file-backed
  SQLite URL, which yields real `Engine` objects without pinning psycopg2),
  plus source-level assertions that `runner.py` and `tasks.py` register at
  all. The **runtime** guarantee for the agent sites is the enumeration
  guard's job under the `agent` project's own test target.
- **The permission is on the wrong role today.** `iam/main.tf:362-378` grants
  `secretsmanager:GetSecretValue` to the *execution* role, which ECS uses to
  resolve `valueFrom` at task start. The application process cannot use it.
  The **task** roles need their own.
- **The enumeration guard has two traps.** (a) Scoping it to `libraries/`
  catches `libraries/test-helper/test_helper/conftest.py:29` and
  `async_db.py:52` — pytest fixtures that must **never** be registered, so the
  guard fails on day one. Scope it to `libraries/utils/utils/` +
  `libraries/agent/agent/`. (b) `utils` and `agent` are separate nx projects
  with independent `test` targets, so a guard living only in
  `libraries/utils/test/` will not run when someone edits only
  `libraries/agent` — precisely the miss it exists to catch.
- `DB_PASSWORD` stays in both task definitions — it is the fallback
  `.current()` returns to, and what makes the rollout reversible. Removing it
  is explicitly NOT in scope.
- **This story touches `libraries/`, so a `main` push does run the deploy
  lane** (unlike rsh104 and rsh107) — but the *enablement* step is a
  task-definition change, i.e. terraform-only, so it needs Force Deploy.
- Verification type: tests-after (plus the T6.3b addition to E-6's named P0
  artifact, which is tests-first).
- Full context: `_devx/workstreams/rotation-self-heal/plan.md` §Phase 6.

## Status log

- 2026-07-27T12:35 — emitted from plan 462355 at RED-gate PASS. T6.3b's
  RED-time assertions live in
  `libraries/utils/test/test_db_credential_provider.py`
  (`test_real_engine_modules_are_inert_when_arn_unset`,
  `test_database_module_registers_all_three_of_its_engine_sites`,
  `test_agent_engine_sites_register_too`) and are observed failing; the
  plan-mechanism correction above is recorded rather than silently applied.
