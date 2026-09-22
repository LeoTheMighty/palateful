<!-- refined: critique 2026-07-27 (lenses: pm, architect, dev, qa) -->

# Plan — Rotation Self Heal

<!-- Stage: Plan. Gate: `devx gate coverage 462355` (plan mode — one row per
     E-id; P0 floor: every P0 expectation `full` and naming a runnable
     artifact). Sizing rule: a phase is one cohesive concern with a
     verifiable exit, sized to land as a single reviewable PR. One phase ≙
     one dev spec ≙ one PR ≙ one tour. -->

## Current state

- **`main` is un-deployable.** `flutter-test` (`ci.yml:304`) is a root job
  with no `needs:`, and sits in the `needs:` list of both `deploy-web`
  (`ci.yml:462`) and `detect-changes` (`ci.yml:521`). Its 3 failures skip
  every deploy job. Prod runs image `c85e350` from 2026-04-26.
- **The deploy lane is nx-affected-gated.** `detect-changes` emits
  `services_to_build=[]` unless api/worker/migrator/parser is affected
  (`ci.yml:592-604`); `deploy-images` is gated on
  `services_to_build != '[]'` (`ci.yml:641-643`); `terraform-prod` requires
  `deploy-images.result == 'success'` (`ci.yml:703-705`); `deploy-services`
  additionally requires `api == 'true' || worker == 'true'`
  (`ci.yml:845-851`). **A commit that touches only `app/` or only
  `terraform/` cannot reach any deploy job.** Terraform-only changes land
  via `.github/workflows/force-deploy.yml` (`workflow_dispatch`), which the
  `ci.yml:698-701` comment names explicitly.
- **`terraform apply` is unattended.** `terraform-prod` runs
  `terraform plan -no-color` (`ci.yml:739`) then
  `terraform apply -auto-approve -input=false` (`ci.yml:748`); nothing
  consumes the plan output. The first push that makes a service affected
  applies **everything** pending since 2026-04-26.
- **The health endpoint cannot see a rotation.**
  `services/api/src/routers/v1/health_router.py:15-28` probes a *pooled*
  connection via `Depends(get_async_database)` (`:17`, `:24`) — pooled
  connections stay authenticated across a rotation — and catches bare
  `Exception` → 503 (`:25-27`), which is a mass-task-replacement hazard.
  Both are on `main` and undeployed.
- **Credentials resolve once, at task start.**
  `terraform/environments/prod/main.tf:228` passes `db_master_secret_arn`
  into the ecs module; `modules/ecs/main.tf:306` and `:426` turn it into a
  `valueFrom` secret, so `DB_PASSWORD` is baked into the container
  environment and never re-read.
- **Five long-lived-process engine construction sites** exist, none of which
  re-resolve a password: `libraries/utils/utils/services/database.py:43`
  (sync `db_engine`), `:91` (`create_async_engine`), `:121`
  (`error_log_engine`), `libraries/agent/agent/runner.py:25`, and
  `libraries/agent/agent/tasks.py:28`. All three set `pool_recycle=3600`
  (`database.py:48`, `:96`, `:125`) — the mechanism that masks a rotation
  failure for up to an hour before the pool turns over.
- **The worker has no health check.** `terraform/modules/ecs/main.tf:396-444`
  defines the worker container with no `healthCheck` block, so ECS reports
  `healthStatus: UNKNOWN`. The image has no HTTP surface (Celery only), and
  `libraries/utils/pyproject.toml` declares **neither** `psycopg2` nor
  `asyncpg` — only `services/worker/pyproject.toml:11,18` do.
- **Both services run with `deployment_minimum_healthy_percent = 0`**
  (`modules/ecs/main.tf:371`, `:473`), so a simultaneous health-check
  failure across all tasks drains the service completely.
- **No Lambda / EventBridge / scheduled-workflow pattern exists.** Verified:
  zero `aws_lambda_function`, `aws_cloudwatch_event_rule`, or `archive_file`
  anywhere under `terraform/`. The `archive` provider is declared in no
  `required_providers` block and appears in no lock file — 
  `terraform/environments/prod/main.tf:6-11` declares only `hashicorp/aws`.
- **Nothing reads Secrets Manager from Python.** Verified: the only
  `secretsmanager` hits across `services/`, `libraries/`, `tools/`,
  `scripts/` are transitive `poetry.lock` extras.
- **`bin/prod-status:15-18`** already calls
  `aws ecs describe-services --cluster palateful-prod --services palateful-api-prod palateful-worker-prod`,
  but reports only desired/running counts — never which image is deployed.

## Desired state

- A push to `main` that touches a service reaches `deploy-services`, subject
  only to the `environment: production` reviewer approval that every
  deploy-touching job already carries (`ci.yml:463`, `:706`, `:852`).
- `GET /v1/health` opens a **fresh** connection and returns 503 **only** on
  a positively-identified auth failure (SQLSTATE `28P01`/`28000`); every
  other error, including an unhandled one, returns 200.
- An `AWSCURRENT` label move on the RDS-managed secret forces a new
  deployment of both ECS services, with no human in the loop.
- Every long-lived engine re-resolves the password at connect time from
  Secrets Manager (TTL-cached, one invalidate-and-retry on auth failure)
  when `DB_PASSWORD_SECRET_ARN` is set — and is byte-identical to today when
  it is not.
- The worker reports a real `healthStatus`, not `UNKNOWN`, and cannot
  crash-loop because the probe itself failed to start.
- A deploy freeze surfaces within 24h of crossing 7 days, both on a
  schedule and on demand from `bin/prod-status`.
- G-2 and G-3 have **measured actuals from a real rotation**, on both the
  connect-time path and the detection-backstop path.

## Deadline shape

G-1 sets **2026-07-29** (`prd.md:44-45`) — the next scheduled rotation under
the current 7-day cadence. Phases 1–4 are deadline-bound; Phases 5–9 land
after. The `rotate_immediately = false` setting
(`terraform/modules/rds/main.tf:203`) means the 90-day cadence is computed
from the last rotation (2026-07-21), so **if the apply slips past 07-29, a
7-day rotation fires against FR-2 + FR-4 only**, with FR-5 not yet landed.
That is a survivable state — it is exactly the pre-deadline scope the user
locked at Design — but it must be a known state, not a surprise.

## Behavior changes shipped incidentally

- **Production rotation cadence moves 7d → 90d.** `e74303f` (2026-05-03)
  already authored `aws_secretsmanager_secret_rotation.db_master` at 90 days
  (`terraform/modules/rds/main.tf:105-118`, `:201-208`), undeployed only
  because `main` has been un-deployable. It lands on the **first
  `terraform apply`** — which is **Phase 2's** push, not Phase 4's, because
  `terraform-prod` auto-applies whenever a service is affected. Decided at
  Design; recorded in `prd.md:60-77`. Consequence: after Phase 2, the next
  natural rotation is ~2026-10, and the self-heal path is exercised ~4×/year
  rather than weekly — which is why Phase 9 exists.

## What we're NOT doing

- The repo-wide hardcoded-date sweep in Flutter tests (39 files under
  `app/test/` carry `2026-0*` literals on the same 30-day fuse). Phase 1
  covers only what blocks the deploy graph, plus a guard against the fuse
  re-lighting mid-workstream.
- `services/migrator` credential resolution — a short-lived task where
  start-time resolution is correct, and whose task role carries zero
  policies today (`iam/main.tf:572-592`).
- **Short-lived Python entrypoints that build their own engines**:
  `services/api/src/manage.py:72`, `services/api/scripts/{promote_admin,
  fetch_feedback,inspect_user_push,analyze_latency,audit_errors}.py`,
  `scripts/backfill_vibes.py`, `services/migrator/migrations/env.py`. Each
  resolves at process start and exits — the same rationale as the migrator.
  Accepted cost, stated plainly: **an operator running these ops scripts
  during a rotation window will hit the auth failure directly.** Registering
  them is a candidate follow-up, not this workstream.
- `libraries/test-helper` engines (`test_helper/conftest.py:29`,
  `test_helper/async_db.py:52`) — pytest fixtures that must **never** get a
  Secrets Manager listener.
- RDS IAM database authentication.
- The Flutter client's error surface (`login_screen.dart:96`).
- Hardening `services/parser/Dockerfile.batch` **beyond what unblocks the
  deploy graph** (see Phase 2, T2.9).
- General Celery liveness (a wedged consumer, a lost broker connection).
- General CI health beyond the jobs gating `deploy-services` / `deploy-web`.
- Removing `DB_PASSWORD` from the task definitions after FR-5 lands — it
  stays as the fallback that makes the rollout reversible.
- Raising `deployment_minimum_healthy_percent` above 0 (see Phase 2's
  accepted risk).

## Expectation coverage

| E-id | Priority | Verified in phase | Validation type | Eval artifact | Coverage |
|---|---|---|---|---|---|
| E-1 | P0 | 1, 2 | tests-first | `app/test/features/activity/imports_tab_test.dart` | full |
| E-2 | P0 | 2 | tests-first | `services/api/tests/test_health.py` | full |
| E-3 | P0 | 2 | tests-first | `services/api/tests/test_health.py` | full |
| E-4 | P1 | 2 (+7 worker path) | tests-first | `services/api/tests/test_health.py` | full |
| E-5 | P0 | 3 | tests-first | `libraries/utils/test/test_rotation_redeploy_handler.py` | full |
| E-6 | P0 | 5, 6 | tests-first | `libraries/utils/test/test_db_credential_provider.py` | full |
| E-7 | P2 | 8 | human | `evals/E-7_deploy-freeze-visibility.md` | full |
| E-8 | P1 | 7 | human | `evals/E-8_worker-healthcheck.md` | full |

**Why two E-ids span two phases.**

- **E-1** (`expectations.md:17-18`) has a two-part threshold: `flutter-test`
  reports 0 failures, **and** `deploy-services` reaches `success`. Phase 1
  can only prove the first half — a commit touching only `app/` leaves
  `services_to_build` empty, so every deploy job skips (`ci.yml:641-643`,
  `:703-705`, `:845-851`). The second half is proven by Phase 2, the first
  phase that touches `services/api` and therefore actually runs the deploy
  lane. Splitting E-1 across the two is honest; forcing Phase 1 through the
  deploy graph would ship the un-fixed `health_router.py` mass-replacement
  hazard, which Phase 2 exists to remove.
- **E-6** (`expectations.md:84-86`) has a two-part threshold: the retry
  semantics (provable in isolation, Phase 5) **and** "engine construction is
  unchanged" with `DB_PASSWORD_SECRET_ARN` unset. The second clause is
  vacuous in Phase 5, where zero call sites are wired — it only becomes
  meaningful once Phase 6 wires all five. So Phase 6 **extends the same
  named artifact** (`libraries/utils/test/test_db_credential_provider.py`)
  with an integration case that imports the real `database.py`, `runner.py`
  and `tasks.py` modules with the variable unset and asserts, against the
  live engines, that **0** Secrets Manager clients were constructed and
  **0** `do_connect` listeners registered (T6.3b). Both halves of the
  threshold therefore land in the P0 artifact rather than resting on
  Phase 6's `tests-after` proxies.

**How E-4's connection budget is met on both probe paths.** E-4's threshold
("at most 1 fresh connection per 60s window regardless of probe rate")
applies to every probe consumer, not just the API, and two paths would
otherwise exceed it. Both are closed by construction rather than left to
measurement:

- **API path (Phase 2)** — two in-process checkers (container 30s
  `ecs/main.tf:318-324`, ALB 60s `alb/main.tf:64`) against a 60s TTL can
  otherwise produce 2 connects in a sliding 60s window when adjacent misses
  race. The cache is therefore **single-flight**: concurrent and adjacent
  misses coalesce onto one in-flight connection. Pass condition: ≤1 connect
  per TTL period under an interleaved 30s/60s probe schedule, not merely
  under a burst.
- **Worker path (Phase 7)** — each `CMD-SHELL` invocation is a cold process,
  so the in-process cache cannot apply and a 30s interval would mean 1
  connect (and, post-FR-5, 1 `get_secret_value`) every 30s. Resolved by
  **pinning the worker `healthCheck.interval` to 60s**, which satisfies the
  threshold by construction and needs no on-disk cache. Pass condition:
  measured connects/hour ≤ 60 and `get_secret_value`/hour ≤ 60 per task.

**How the classification thresholds are actually tested.** E-2 and E-3 name
`services/api/tests/test_health.py`, and their thresholds are stated in
SQLSTATEs (`28P01`/`28000`) — which the router never sees. The seam is
therefore **the connection attempt, not the verdict**: API tests patch the
probe's connect call to raise real `OperationalError` instances carrying
those SQLSTATEs, so `is_auth_error` executes for real inside the API test
and the full classify→verdict→status chain is exercised end to end. Mocking
`cached_verdict_async` directly would test only an enum-to-int mapping and
would not satisfy the threshold. Same seam makes E-4 measurable: count
invocations of the patched connect across N rapid probes. Supporting
table-driven classifier tests also land in
`libraries/utils/test/test_db_credentials.py`, but the named artifact stays
authoritative.

**On Phase 9 and the goal-level evidence.** Phase 9 owns no E-id; it
re-measures E-2's, E-5's, and E-6's thresholds against production rather
than against mocks, and it is where G-2, G-3 and G-4 get numeric actuals.
This answers the Design stage's carry-in — the 5 design-mode partials
(G-1..G-4, CAP-1) were all "unproven until CI actually runs green and until
a real rotation is observed." G-1 and CAP-1 are proven by Phases 1–2; the
rest by Phase 9.

## Phase checklist

- [ ] Phase 1: Unblock the deploy path on `main` (FR-1) — **by 2026-07-29**
- [ ] Phase 2: Credential-aware health probe (FR-2) — **by 2026-07-29**
- [ ] Phase 3: Rotation-redeploy Lambda handler (FR-4a) — **by 2026-07-29**
- [ ] Phase 4: EventBridge rule + Lambda infrastructure (FR-4b) — **by 2026-07-29**
- [ ] Phase 5: Secrets Manager password provider (FR-5a)
- [ ] Phase 6: Engine-site registration + task-role IAM (FR-5b)
- [ ] Phase 7: Worker health check (FR-3)
- [ ] Phase 8: Deploy-freeze visibility (FR-6)
- [ ] Phase 9: Rotation drill — measure G-2, G-3, G-4

## Phases

### 1. Phase: Unblock the deploy path on `main` (FR-1)

**Overview**: Nothing else in this workstream can reach production until
`flutter-test` is green. Narrow by design — and it is the empirical answer
to whether the 2026-05-03 `deploy-web` failure still reproduces, which no
amount of reading settles.

**Files**:
- `app/test/features/activity/imports_tab_test.dart` — make the
  `completed` / `skipped` fixture timestamps relative to `DateTime.now()`
  instead of the hardcoded `2026-04-18T10:*` literals. The three failing
  `testWidgets` are at `:211`, `:425`, `:462`; their affected fixtures are
  at `:277`, `:445`, `:518`, and `:525`. (`:510` is `item-buried-review`,
  status `awaiting_review` — age-independent; leave it alone.)
- `.github/workflows/ci.yml` — **conditional**, only if the first
  `deploy-web` run reveals the 2026-05-03 failure still reproduces: pin
  `flutter-version` (`:467-470`) and `wrangler@latest` (`:493`).
- A grep-guard test (location: `app/test/`) failing on any new hardcoded
  year literal in a `created_at` fixture.

**Context**:
- The 30-day cutoff is **intentional product behavior**, commented at
  `app/lib/features/activity/imports_tab.dart:165-167` and applied at
  `:168` (`DateTime.now().subtract(const Duration(days: 30))`) to
  `completed` (`:183-189`) and `skipped` (`:190-195`). **The fix belongs in
  the test, not the widget.** Changing the widget to satisfy a stale fixture
  would delete a shipped product decision.
- **Two masked assertions, not one.** The run aborts at `:542`
  (`expect(find.text('Done'), findsOneWidget)`), so both `:543`
  (`find.text('Skipped photo')`) and `:544`
  (`find.textContaining('Skipped · 1')`) are currently unreached and sit on
  the same fuse.
- **This phase cannot reach `deploy-services`, and must not try.** An
  `app/`-only commit leaves `services_to_build` empty. `deploy-web` *does*
  run (it needs `flutter-test`, and `app` is affected), so the 2026-05-03
  `deploy-web` question is answerable here; the `deploy-images (parser)`
  question is not, and moves to Phase 2.
- 39 test files share the date fuse; the guard exists so one of the other 36
  crossing the cutoff mid-workstream does not silently re-red `flutter-test`
  and skip the deploy graph for every remaining phase.

**Verification plan**:
- Type: tests-first (the failing tests already exist; this is fixture repair
  against a pre-existing RED)
- Success criteria:
  - `cd app && flutter test` reports **0 failures** (currently 3 of 1524 —
    confirmed by running the suite).
  - The previously-masked assertions at `:543` and `:544` both run and pass.
  - Fixture timestamps contain no hardcoded year literal, and the grep guard
    fails when one is reintroduced.
  - On the `main` push: `flutter-test` green, `deploy-web` reaches
    `success`, and `detect-changes` **runs** (not skipped).
  - E-1's `deploy-services` half is explicitly deferred to Phase 2 and said
    so in the status log — not silently dropped.

**Tasks**:
- [ ] T1.1 Reproduce the 3 failures locally and capture the output — files: `app/test/features/activity/imports_tab_test.dart`
- [ ] T1.2 Replace the `completed`/`skipped` fixture timestamps (`:277`, `:445`, `:518`, `:525`) with `DateTime.now()`-relative values; leave `awaiting_review`/`failed` fixtures alone (age-independent by design)
- [ ] T1.3 Confirm the previously-masked `:543` **and** `:544` assertions now run and pass
- [ ] T1.4 Add the hardcoded-year grep guard over `app/test/`
- [ ] T1.5 Push to `main`; watch `flutter-test` → `deploy-web` → `detect-changes`
- [ ] T1.6 Record the 2026-05-03 `deploy-web` outcome — reproduced or not — in the spec status log; if reproduced, pin the two unpinned versions and re-run

---

### 2. Phase: Credential-aware health probe (FR-2)

**Overview**: Replace the pooled-connection, bare-`except` probe with a
fresh-connection probe that returns 503 **only** on a positively-identified
auth failure. This is also the phase that carries the **first
`terraform apply` since 2026-04-26** and the first real exercise of the
deploy lane — so it is doing three risky things at once, and its task list
reflects that.

**Files**:
- `libraries/utils/utils/services/db_credentials.py` — **new**. This phase
  creates the module with `is_auth_error(exc) -> bool` only; Phase 5 extends
  the same file with the provider and the registration helper.
- `libraries/utils/utils/services/db_probe.py` — **new**. `ProbeVerdict`
  enum, `probe_async`, `probe_sync`, `cached_verdict_async(ttl_s=60)`, a
  `_reset_verdict_cache()` test seam, and a `__main__` CLI (see Phase 7 for
  its hardening contract).
- `services/api/src/routers/v1/health_router.py` — rewrite `health_check`
  to read the cached verdict. **Drop the `Depends(get_async_database)`
  parameter** (`:17`) — a pooled connection structurally cannot observe the
  failure.
- `services/api/tests/test_health.py` — E-2, E-3, E-4.
- `services/api/tests/conftest.py` — autouse fixture resetting the probe
  verdict cache.
- `libraries/utils/test/test_db_credentials.py` — supporting table-driven
  classifier tests.

**Context**:
- **`is_auth_error` must match the raw DBAPI error, not only `.orig`.** In
  Phase 5's `do_connect` listener the exception from
  `dialect.connect(*cargs, **cparams)` is the **unwrapped** DBAPI error —
  SQLAlchemy wraps only above the pool creator. Additionally, psycopg2
  connect-time `OperationalError`s are produced by libpq without a
  `PGresult`, so `.pgcode` is commonly `None`. Contract: check `exc`, then
  `.orig`, then `__cause__`; match `sqlstate`/`pgcode` **or** a message
  pattern (`password authentication failed`, `no password supplied`).
  Verify against a **live** psycopg2 auth failure (docker-compose Postgres,
  wrong password), not only a hand-built mock.
- **Probe URL source and the unset case.** The probe reads
  `utils.constants.ASYNC_DATABASE_URL` / `DATABASE_URL`. `DATABASE_URL` is
  `""` in the API test env (`services/api/tests/conftest.py:15`) and
  `database.py:79-80` returns `(None, None)` on a falsy async URL.
  Contract: **unset URL → `OK`** (nothing to authenticate against). Getting
  this wrong breaks `test_main.py:46` and `test_async_client_fixture.py:15`.
- **The verdict cache is process-global.** `conftest.py:1485`,
  `test_main.py:46` and `test_async_client_fixture.py:15` all hit
  `/v1/health`; a leaked `AUTH_FAILED` verdict makes them order-dependent.
  The reset fixture is not optional.
- **`test_health_check_db_failure` (`test_health.py:11-16`) inverts.** It
  currently asserts a `RuntimeError` produces `503 {"detail": "db unavailable"}`.
  Under FR-2's fail-open rule an unclassified exception must return **200**.
  Deliberate behavior change — call it out in the PR body and the tour's
  decision ledger.
- **The 503 body must identify the failure as credential-related**
  (`expectations.md:31`); today it is `{"detail": "db unavailable"}`
  (`health_router.py:27`), which does not. Specify
  `{"detail": "db credentials invalid", "db": "AUTH_FAILED"}` and assert it.
  The 200 body gains a `db` field carrying the verdict name, which breaks
  `test_health_check`'s exact-body assertion (`:4-8`) — update it.
- **`services/api` enforces 100% coverage** (`services/api/pyproject.toml:43`,
  `fail_under = 100`, `source = ["src"]`). `libraries/utils` sets no
  `fail_under` (`libraries/utils/pyproject.toml:5-7`) — so the probe and
  classifier, the highest-risk new code, land where nothing enforces
  coverage. T2.8 compensates.
- `libraries/utils` tests live in `libraries/utils/test/` (singular, no
  `conftest.py`). `libraries/utils/pyproject.toml:9-11` supplies its own
  `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, so pytest's
  rootdir resolves there and **that** config wins — the root config never
  applies. Note `:10` also injects `--cov` with cwd-relative report paths.
- `poolclass=NullPool` is the point, not an optimization — every probe must
  be a genuinely new connection and TLS handshake.
- **Accepted risk, stated explicitly.** Both services set
  `deployment_minimum_healthy_percent = 0` (`ecs/main.tf:371`, `:473`) and
  the ALB matches only `200` with `unhealthy_threshold = 3` at 60s
  (`alb/main.tf:58-71`). A real rotation makes every task's probe fail at
  once, so all targets deregister simultaneously. That **is** the intended
  self-heal, and the fail-open classifier is what keeps it from firing on a
  transient blip — but the API-unavailable window during a genuine rotation
  is bounded only by task replacement time, and is not measured until
  Phase 9. Raising `deployment_minimum_healthy_percent` is named in
  "NOT doing"; revisit at the Outcome review.
- **`run-migrator` is the next unproven link.** It gates `deploy-services`
  (`ci.yml:850`) and runs whenever migrator is affected — and
  `services/migrator` implicitly depends on `utils`, so touching
  `libraries/utils` makes it run for the first time since 2026-04-26.
- No Terraform change is needed for the detection path: the container health
  check (`ecs/main.tf:318-324`) and the ALB target group already turn a 503
  into a task replacement.

**Verification plan**:
- Type: tests-first
- Success criteria:
  - 503 returned for **both** `28P01` and `28000`, raised as real
    `OperationalError`s at the patched connect seam; body identifies the
    failure as credential-related (E-2).
  - 200 returned for a timeout, an `OperationalError` with a non-auth
    SQLSTATE, a DNS resolution failure, **and** a bare `RuntimeError`
    (E-3 — the fail-open floor).
  - `is_auth_error` classifies a **live** psycopg2 connect-time auth failure
    correctly, not just a constructed exception.
  - At most **1** fresh connection per 60s window regardless of probe rate
    (E-4), asserted by counting patched-connect invocations. Two distinct
    cases must both pass: a rapid burst of N probes, **and** an interleaved
    30s/60s schedule crossing a TTL boundary — the latter passes only if the
    cache is single-flight, so it is the case that actually tests the design.
  - `test_main.py`, `test_async_client_fixture.py` and the `conftest.py`
    example still pass, in any test order.
  - `npx nx run api:test` passes with coverage still at 100%; the utils
    coverage assertion in T2.8 passes.
  - **On the `main` push**: `deploy-images` runs all four legs,
    `run-migrator` succeeds, `terraform-prod` succeeds, and
    `deploy-services` reaches conclusion `success` — closing E-1's second
    half.

**Tasks**:
- [ ] T2.1 **Before merging**: run `terraform plan` locally against `terraform/environments/prod` and review the full pending diff line by line. Paste it into the spec status log with the `aws_secretsmanager_secret_rotation.db_master` line explicitly called out. This is the only review gate before an unattended `-auto-approve` applies everything pending since 2026-04-26
- [ ] T2.2 Create `db_credentials.py` with `is_auth_error` per the contract above (exc → `.orig` → `__cause__`; SQLSTATE **or** message pattern) — files: `libraries/utils/utils/services/db_credentials.py`
- [ ] T2.3 Verify the classifier against a live docker-compose Postgres auth failure on **both** psycopg2 and asyncpg
- [ ] T2.4 Create `db_probe.py`: `NullPool` engine, `probe_async`/`probe_sync`, **single-flight** TTL-cached verdict, `_reset_verdict_cache()`, unset-URL → `OK`
- [ ] T2.5 Rewrite `health_check`; remove the `get_async_database` dependency; specify both the 200 and the 503 bodies
- [ ] T2.6 Add the autouse cache-reset fixture — files: `services/api/tests/conftest.py`
- [ ] T2.7 Rewrite `test_health.py` for E-2/E-3/E-4 at the connect seam, inverting `test_health_check_db_failure` and updating `test_health_check`'s body assertion
- [ ] T2.8 Add a coverage assertion over `coverage/libraries/utils/coverage.xml` for `db_credentials.py` and `db_probe.py`, so "tests-first" stays enforceable in a package with no `fail_under`
- [ ] T2.9 Make `DB_PROBE_TTL_S` configurable (default 60) — it trades directly against E-4
- [ ] T2.10 Push; watch the full deploy graph. Record the `deploy-images (parser)` outcome; if it reproduces, pin the unpinned fetches in `services/parser/Dockerfile.batch` **inside this phase** (FR-1 requires it resolved or confirmed-gone, and it blocks every remaining phase)
- [ ] T2.11 Confirm the rotation-cadence resource actually applied, and record the new next-rotation date

---

### 3. Phase: Rotation-redeploy Lambda handler (FR-4a)

**Overview**: The handler as pure, unit-testable Python — separated from its
infrastructure so E-5's thresholds are provable without an AWS round-trip.

**Files**:
- `libraries/utils/utils/services/rotation_redeploy.py` — **new**.
  `handler(event, context) -> dict`: validate the event targets the
  configured secret, then `update_service(cluster, service, forceNewDeployment=True)`
  once per service, aggregating failures into
  `{"redeployed": [...], "failed": [...]}`.
- `libraries/utils/test/test_rotation_redeploy_handler.py` — **new**, E-5.

**Context**:
- **Hard constraint: stdlib + boto3/botocore only.** No `utils` internal
  imports, no relative imports, no other third-party packages — even though
  the file lives inside the `utils` package. Phase 4 packages it with
  `data "archive_file"` using `source_file`, so the zip contains exactly
  this one module at the zip root. A `from . import x` breaks the deploy,
  not the test.
- **Lambda contract, pinned here so Phase 4 cannot guess**: runtime
  `python3.13` (matching `^3.13` across every `pyproject.toml`), handler
  string `rotation_redeploy.handler`.
- Env config: `ECS_CLUSTER`, `ECS_SERVICES`, `WATCHED_SECRET_ARN` — all
  required; the handler errors when absent.
- Partial failure must be **visible**, not swallowed — the difference
  between a working backstop and a silent one, which is the exact failure
  class this workstream exists to remove.
- The action itself is proven: `deploy-services` already runs
  `aws ecs update-service --force-new-deployment` (`ci.yml:902`).
- There is precedent for AST-based import guards in
  `libraries/utils/test/test_async_engine_guard.py` and
  `test_database_api_frozen.py` — follow it.

**Verification plan**:
- Type: tests-first
- Success criteria (all E-5):
  - `update_service` called **exactly 1 time per service** (2 calls total),
    each with `forceNewDeployment=True`.
  - A non-matching secret ARN produces **0** calls.
  - A partial failure (one service raises) yields a non-0 handler result
    with the failing service named in `failed`.
  - Missing required env raises rather than silently no-op'ing.
  - **AST guard**: every top-level import in `rotation_redeploy.py` resolves
    to stdlib or `boto3`/`botocore` — asserted positively, so a relative
    import or a stray third-party dependency fails too.

**Tasks**:
- [ ] T3.1 Write `test_rotation_redeploy_handler.py` against a stubbed boto3 ECS client, covering all four E-5 thresholds — files: `libraries/utils/test/test_rotation_redeploy_handler.py`
- [ ] T3.2 Implement `handler` to make them pass
- [ ] T3.3 Add the AST import-hygiene guard (stdlib ∪ {boto3, botocore} only), following the existing guard tests
- [ ] T3.4 Record the pinned runtime + handler string in the spec so Phase 4 consumes rather than invents them
- [ ] T3.5 Run `poetry run pytest libraries/utils/`

---

### 4. Phase: EventBridge rule + Lambda infrastructure (FR-4b)

**Overview**: The first Lambda and the first EventBridge rule in this repo.
Separated from Phase 3 because its risk is entirely different: not "does the
code work" but "does the rule ever fire".

**Files**:
- `terraform/modules/rotation-redeploy/main.tf` — **new**.
  `aws_cloudwatch_event_rule` scoped to the secret ARN and the `AWSCURRENT`
  label move; `aws_lambda_function` (runtime `python3.13`, handler
  `rotation_redeploy.handler`) packaged via `data "archive_file"`
  (`source_file`); `aws_cloudwatch_event_target`; `aws_lambda_permission`;
  execution role with `ecs:UpdateService` + `ecs:DescribeServices` on the
  two service ARNs, plus CloudWatch Logs.
- `terraform/modules/rotation-redeploy/variables.tf`, `outputs.tf` — **new**.
- `terraform/environments/prod/main.tf` — declare the `archive` provider in
  `required_providers` (`:6-11` currently has only `aws`) and wire the
  module. `module.rds.db_master_secret_arn` is already an output
  (`modules/rds/main.tf:235-238`) and already consumed at `:228`.
- `terraform/environments/prod/.terraform.lock.hcl` — regenerated to include
  `hashicorp/archive`.

**Context**:
- **The `archive` provider is declared and locked nowhere.**
  `terraform/environments/prod/main.tf:6-11` lists only `hashicorp/aws`, and
  the lock file contains exactly one provider block. CI runs
  `terraform init -backend-config=...` (`ci.yml:734`) against the committed
  lock — an undeclared provider fails there, and an unregenerated lock
  mutates on the runner. Declare it and commit the regenerated lock.
- **This phase is Terraform-only, so CI will not apply it.**
  `terraform-prod` requires `deploy-images.result == 'success'`
  (`ci.yml:703-705`), and `deploy-images` skips when `services_to_build` is
  `[]` (`ci.yml:641-643`). The `ci.yml:698-701` comment says so outright.
  Apply via **Actions → Force Deploy** (`workflow_dispatch`,
  `force-deploy.yml`), which rebuilds all four images at HEAD, applies
  terraform, and carries its own `environment: production` reviewer gate.
- **CI will not validate this module either.** `ci.yml:442-448` runs
  `terraform init`/`validate` against `terraform/environments/dev`, which
  declares only vpc/s3/ecr/iam/batch — no rds, no ecs, and it will never see
  `rotation-redeploy`. Only `terraform fmt -check -recursive`
  (`ci.yml:439-440`) covers the new files. **Reviewing the plan output at
  apply time is the real gate.**
- **The event shape is the open risk.** The `detail-type` string and
  `detail` field names for Secrets Manager's "Secret Label Updated" have not
  been confirmed against a live event. An `ENABLED` rule with a non-matching
  pattern is **indistinguishable from a working one** — the same silent
  failure this workstream exists to remove. The CloudTrail
  `RotationSucceeded` signal (observed at 2026-07-21T21:29:14 in this
  incident) is the proven fallback pattern.
- Both ECS services run a deployment circuit breaker with rollback
  (`modules/ecs/main.tf:366-369`, `:468-471`).
- The cadence change already applied in Phase 2 — do not expect it here.

**Verification plan**:
- Type: human
- Success criteria:
  - `terraform fmt -check -recursive terraform/` passes; `terraform init`
    succeeds against the committed lock file with no lock mutation.
  - `terraform plan` output pasted into the spec status log, reviewed, and
    confirmed to contain only this module's resources.
  - **End-to-end proof, not just existence**: a published test event (or a
    forced rotation) produces a Lambda invocation and **two**
    `ecs:UpdateService` calls, visible in CloudWatch Logs / CloudTrail. An
    `ENABLED` rule alone is not a passing criterion.
  - The actual event JSON that matched is recorded in the spec status log.
  - The Lambda zip contains exactly one `.py` file at the zip root.

**Tasks**:
- [ ] T4.1 Capture or confirm the real `Secret Label Updated` event JSON; record it. If unconfirmable, switch to the CloudTrail `RotationSucceeded` pattern and say so
- [ ] T4.2 Declare `archive = { source = "hashicorp/archive" }` in the module and in `terraform/environments/prod/main.tf`; run `terraform init -upgrade`; commit the regenerated lock file
- [ ] T4.3 Write the module (`main.tf`, `variables.tf`, `outputs.tf`) using the runtime + handler string pinned in T3.4 — files: `terraform/modules/rotation-redeploy/`
- [ ] T4.4 Wire it into `terraform/environments/prod/main.tf`, passing `module.rds.db_master_secret_arn` and both service ARNs
- [ ] T4.5 `terraform fmt -recursive`; confirm CI's fmt gate passes
- [ ] T4.6 **Apply via Actions → Force Deploy** (`workflow_dispatch`) — a `main` push will not apply a terraform-only change. Review the plan step's output before approving the apply
- [ ] T4.7 Publish a matching test event; confirm rule → Lambda → two `UpdateService` calls end to end
- [ ] T4.8 Confirm the resulting deployments settle and the circuit breaker did not roll back

---

### 5. Phase: Secrets Manager password provider (FR-5a)

**Overview**: The credential machinery as a standalone, fully-tested library
surface, with **zero call sites wired**. Merging this changes no runtime
behavior anywhere — which is what makes Phase 6's wiring reviewable on its
own terms.

**Files**:
- `libraries/utils/utils/services/db_credentials.py` — extend the Phase 2
  module with `SecretPasswordProvider(secret_arn, ttl_s=300, client=None)`,
  `.current()`, `.invalidate()`, `resolve_password_provider()`, and
  `register_rotating_credentials(engine) -> bool`.
- `libraries/utils/test/test_db_credential_provider.py` — **new**, E-6.

**Context**:
- **Do not put the Secrets Manager client in `aws.py`.** `AWSService.__init__`
  (`libraries/utils/utils/services/aws.py:13-37`) builds `_s3` and `_batch`
  **unconditionally**, sharing one `Config(signature_version="s3v4",
  read_timeout=2.0, retries={"max_attempts": 2})` tuned to an S3 NFR budget.
  Adding the SM client there would construct it on every `AWSService()`
  instantiation regardless of `DB_PASSWORD_SECRET_ARN` — directly violating
  E-6's "0 Secrets Manager calls, 0 clients constructed" threshold, and
  saddling a connect-path credential fetch with an S3 signature version and
  a 2s read timeout. Construct it **lazily inside `db_credentials.py`** with
  its own `Config`; the provider's `client=` parameter is reserved for tests.
- The registration helper attaches SQLAlchemy's `do_connect` event:
  ```
  do_connect(dialect, conn_rec, cargs, cparams):
      cparams["password"] = provider.current()
      try:
          return dialect.connect(*cargs, **cparams)
      except Exception as exc:
          if not is_auth_error(exc):
              raise
          provider.invalidate()                        # exactly one
          cparams["password"] = provider.current()
          return dialect.connect(*cargs, **cparams)    # exactly one retry
  ```
  Returning a connection from `do_connect` suppresses SQLAlchemy's own
  connect — that is what makes the single retry expressible here instead of
  in every caller. For async engines the listener attaches to
  `engine.sync_engine`. Note the exception here is the **raw DBAPI error**,
  which is why Phase 2's `is_auth_error` must match unwrapped exceptions.
- **`resolve_password_provider()` returns `None` when `DB_PASSWORD_SECRET_ARN`
  is unset, and the helper is then a total no-op** — no boto3 client
  constructed, no listener registered. This is the byte-identical path CAP-6
  requires for local, docker-compose, and CI.
- **The `DB_PASSWORD` fallback must not silently poison the retry.**
  `.current()` falls back to the env var when resolution raises — but on the
  *retry* path that returns the very password that just failed, making a
  Secrets Manager outage indistinguishable from "no rotation occurred".
  Contract: the fallback is legal on the **first** resolution, and on the
  retry path a resolution failure must surface distinguishably (distinct
  exception or logged verdict) rather than re-presenting a known-bad
  credential.
- **FR-5 does not touch `libraries/utils/utils/constants.py:19-42`.**
  `_build_database_url()` stays the single place URLs are composed; the
  listener overrides `cparams["password"]` per connection. Forking URL
  assembly here would undo the 2026-04-15 credential refactor.
- Follow `libraries/utils/test/test_db_pool_constants.py`'s established
  `monkeypatch.setenv` + `importlib.reload` pattern for env-derived state.
- The cached password lives only in memory — never logged, never on disk.

**Verification plan**:
- Type: tests-first
- Success criteria (all E-6):
  - Exactly **1** re-resolution and **1** retry per auth failure; the
    retried connection succeeds.
  - A second consecutive auth failure propagates rather than looping.
  - A **non**-auth exception propagates with **0** re-resolutions.
  - With `DB_PASSWORD_SECRET_ARN` unset: **0** Secrets Manager calls, **0**
    boto3 clients constructed, **0** listeners registered, and
    `register_rotating_credentials` returns `False`.
  - Within the TTL, repeated `.current()` calls make **0** additional
    `get_secret_value` calls; past it, exactly 1.
  - **Composed failure**: auth failure **and** `get_secret_value` raises →
    the retry does not silently re-present the stale `DB_PASSWORD`; the
    failure is distinguishable.
  - `poetry run pytest libraries/utils/` passes; `git diff --stat` touches
    only `db_credentials.py` and the new test — **no call sites**.

**Tasks**:
- [ ] T5.1 Write `test_db_credential_provider.py` covering every threshold above, including the composed SM-outage-during-retry case — files: `libraries/utils/test/test_db_credential_provider.py`
- [ ] T5.2 Implement `SecretPasswordProvider` (TTL cache, JSON key `password`, lazily-constructed client with its own `Config`, first-resolution `DB_PASSWORD` fallback)
- [ ] T5.3 Implement the distinguishable-failure contract on the retry path
- [ ] T5.4 Implement `resolve_password_provider` + `register_rotating_credentials`, including the no-provider no-op path
- [ ] T5.5 Make `DB_SECRET_TTL_S` configurable (default 300)
- [ ] T5.6 Extend T2.8's coverage assertion to `db_credentials.py`'s new surface
- [ ] T5.7 Confirm the diff wires **no** call sites

---

### 6. Phase: Engine-site registration + task-role IAM (FR-5b)

**Overview**: Wire Phase 5's helper into all five long-lived engine sites
and grant the task roles the permission they need. Ships **disabled** —
`DB_PASSWORD_SECRET_ARN` stays unset, so merging is a no-op until it is
explicitly set on a task definition.

**Files**:
- `libraries/utils/utils/services/database.py` — register at `:43` (sync
  `db_engine`), `:91` (`create_async_engine`, via `.sync_engine`), and
  `:121` (`error_log_engine`).
- `libraries/agent/agent/runner.py:25` — register on the runner engine.
- `libraries/agent/agent/tasks.py:28` — register on the task engine.
- `terraform/modules/iam/main.tf` — add `secretsmanager:GetSecretValue` on
  the db master secret to `ecs_api_task` (`:416`) and `ecs_worker_task`
  (`:519`), copying the shape of the execution-role policy at `:362-378`.
- `terraform/modules/ecs/main.tf` — add the `DB_PASSWORD_SECRET_ARN`
  environment variable to the api (`:306` region) and worker (`:426` region)
  container definitions, plumbed from `var.db_master_secret_arn`.
- The enumeration guard test (see T6.3 for its required location).

**Context**:
- **`libraries/agent` is the easy miss.** `runner.py:25` and `tasks.py:28`
  each call `create_engine(settings.database_url, pool_pre_ping=True)`
  independently of `utils/services/database.py`. A fix confined to
  `database.py` leaves the worker's agent tasks still failing after a
  rotation — the partial fix that would make the workstream look done while
  the outage recurs.
- **The permission is on the wrong role today.** `iam/main.tf:362-378`
  grants `secretsmanager:GetSecretValue` to the *execution* role, which ECS
  uses to resolve `valueFrom` at task start. The application process cannot
  use it. The **task** roles need their own.
- **The enumeration guard has two traps.** (a) Scoping it to `libraries/`
  catches `libraries/test-helper/test_helper/conftest.py:29` and
  `async_db.py:52` — pytest fixtures that must **never** be registered, so
  the guard fails on day one. Scope it to `libraries/utils/utils/` +
  `libraries/agent/agent/`, with the test-helper exclusion named and
  justified in the test. (b) `utils` and `agent` are separate nx projects
  with independent `test` targets, so a guard living only in
  `libraries/utils/test/` will not run when someone edits only
  `libraries/agent` — which is precisely the miss it exists to catch. It
  must run for both projects.
- **Rollout order is worker-first** (Design § Migration plan step 4): lower
  user impact than the API. Set `DB_PASSWORD_SECRET_ARN` on the worker task
  definition, confirm, then the API. Rollback is unsetting one variable.
- `DB_PASSWORD` stays in both task definitions — it is the fallback
  `.current()` returns to, and what makes the rollout reversible.
- **This phase touches `libraries/`, so a `main` push does run the deploy
  lane** (unlike Phases 4 and 7) — but the *enablement* step is a
  task-definition change, i.e. terraform-only, so T6.7 needs Force Deploy.

**Verification plan**:
- Type: tests-after
- Success criteria:
  - All five long-lived sites register — asserted by the enumeration guard,
    not by reading the diff, so a sixth site added later fails loudly.
  - **E-6's second clause, in E-6's own artifact**: with
    `DB_PASSWORD_SECRET_ARN` unset, importing the real engine modules
    constructs **0** Secrets Manager clients and registers **0** listeners
    across all five wired sites (T6.3b).
  - The guard runs for **both** the `utils` and `agent` nx projects, and
    correctly excludes `libraries/test-helper`.
  - With `DB_PASSWORD_SECRET_ARN` unset: `npx nx run api:test` and
    `poetry run pytest libraries/utils/` produce the same pass counts and
    exit codes as before the change, and `docker compose up` reaches a
    healthy api container (CAP-6).
  - `terraform plan` shows only the two IAM policies and the two env vars.
  - After enabling on the worker: worker tasks reach `RUNNING`, no auth
    errors in `/ecs/palateful-worker-prod`, and
    `audit_errors.py --service worker` shows no new error types.
  - After enabling on the API: `GET /v1/health` returns 200 with `db: OK`.

**Tasks**:
- [ ] T6.1 Register at the three `database.py` sites (`:43`, `:91`, `:121`) — files: `libraries/utils/utils/services/database.py`
- [ ] T6.2 Register at `libraries/agent/agent/runner.py:25` and `libraries/agent/agent/tasks.py:28`
- [ ] T6.3 Add the enumeration guard: AST-scan `libraries/utils/utils/` + `libraries/agent/agent/` for `create_engine`/`create_async_engine`, assert each is registered, exclude `libraries/test-helper` by name with a written reason, and ensure it executes under both projects' `test` targets
- [ ] T6.3b **Close E-6's second clause in its named artifact.** Extend `libraries/utils/test/test_db_credential_provider.py` with an integration case that imports the real `database.py`, `runner.py` and `tasks.py` with `DB_PASSWORD_SECRET_ARN` unset and asserts, against the live engines, **0** Secrets Manager clients constructed and **0** `do_connect` listeners registered — so "engine construction is unchanged" is proven where E-6 points, not by tests-after proxies
- [ ] T6.4 Add the task-role IAM policies — files: `terraform/modules/iam/main.tf`
- [ ] T6.5 Plumb `DB_PASSWORD_SECRET_ARN` into both container definitions — files: `terraform/modules/ecs/main.tf`
- [ ] T6.6 Merge with the variable **unset**; confirm zero behavior change
- [ ] T6.7 Enable on the worker via Force Deploy; observe; then enable on the API
- [ ] T6.8 Verify CAP-3 for the API — force one api task into `AUTH_FAILED` (with `DB_PASSWORD_SECRET_ARN` temporarily unset on it) and confirm ECS replaces it. Nothing else in the plan proves the API replacement half of CAP-3

---

### 7. Phase: Worker health check (FR-3)

**Overview**: Give the worker a health-check mechanism where it has none.
Not on the outage path — FR-5 already removes the credential failure — but
it removes `healthStatus: UNKNOWN`, which is what E-8 measures.

**Files**:
- `libraries/utils/utils/services/db_probe.py` — harden the `__main__` CLI
  per the contract below (the module shipped in Phase 2).
- `terraform/modules/ecs/main.tf` — add a `healthCheck` block to the worker
  container definition (`:396-444`), `CMD-SHELL` invoking
  `python -m utils.services.db_probe`, with a `startPeriod` covering Celery
  boot.
- `evals/E-8_worker-healthcheck.md` — **new**, the E-8 observation record.

**Context**:
- **The CLI must be fail-open against its own failure to start.**
  `python -m utils.services.db_probe` exits non-zero on *any* startup
  problem — ImportError, missing driver, PATH issue — not only
  `AUTH_FAILED`. This is concrete, not hypothetical:
  `libraries/utils/pyproject.toml` declares **neither** psycopg2 nor asyncpg
  (only `services/worker/pyproject.toml:11,18` do), and the worker image
  sets `WORKDIR`/`PYTHONPATH` to `$DOCKER_SERVICE_ROOT/src`
  (`services/worker/Dockerfile:131,133`). Combined with
  `deployment_minimum_healthy_percent = 0` (`ecs/main.tf:473`) and no ALB,
  a probe that cannot start becomes an unbounded crash loop — re-introducing
  the mass-replacement hazard FR-2 exists to remove, on the worker.
  **Contract: catch `BaseException` at the top level, including import
  failure, and exit 0. Exit 1 only on a positively-classified
  `AUTH_FAILED`.**
- **The running worker image must already contain `db_probe`.** It ships in
  Phase 2, but nothing guarantees the *deployed* worker task definition
  points at an image built after that merge. Verify before applying.
- **Cross-process cache cost — and why `interval` is 60s, not 30s.** Each
  `CMD-SHELL` invocation is a cold process, so the in-process TTL cache that
  bounds E-4 on the API path cannot apply: at a 30s interval that would be
  one real DB connect per check and — once FR-5 is enabled — one
  `get_secret_value` per check, ~2,880 SM calls/day/task, which **exceeds
  E-4's threshold**. Resolved by pinning `healthCheck.interval = 60`, which
  satisfies "at most 1 fresh connection per 60s" by construction and avoids
  inventing an on-disk cache. The cost is coarser detection granularity on
  the worker, which is acceptable — the worker is not on the outage path and
  FR-5 is the primary mechanism by this point.
- **This phase is Terraform-only** (plus the CLI hardening in `libraries/`,
  which does trigger the deploy lane) — the `healthCheck` block itself
  applies via Force Deploy if it lands in a terraform-only commit.
- Adding fastapi/uvicorn to a Celery-only image to serve one route is a
  heavier change than the CLI — hence `CMD-SHELL`.
- **Be precise about what this buys.** It establishes the mechanism and
  removes `UNKNOWN`. It does **not** make worker liveness observable in
  general: a Celery consumer wedged on a poisoned task still holds valid
  credentials and still reports `HEALTHY`. Named in "NOT doing".

**Verification plan**:
- Type: human
- Success criteria (E-8):
  - **0** worker tasks report `healthStatus: UNKNOWN` after the deployment.
  - The worker reports `HEALTHY` within **120s** of task start.
  - **Fail-open against self-failure**: renaming/breaking the probe module,
    or removing its DB driver, leaves the task `HEALTHY` — it must never
    crash-loop because the probe could not run.
  - A simulated non-auth DB error does **not** mark the task unhealthy.
  - A genuine `AUTH_FAILED` **does** — run this leg with
    `DB_PASSWORD_SECRET_ARN` temporarily unset on the worker, since FR-5
    would otherwise heal the break within the 300s TTL. State the rollback
    (re-set the variable, force a deployment) before starting.
  - **E-4 on the worker path**: measured connects/hour **≤ 60** and
    `get_secret_value`/hour **≤ 60** per task, confirming the 60s interval
    holds the 1-per-60s budget across cold processes.
  - Actuals in `evals/E-8_worker-healthcheck.md`.

**Tasks**:
- [ ] T7.1 Harden the `__main__` CLI: top-level `BaseException` catch → exit 0; exit 1 only on `AUTH_FAILED` — files: `libraries/utils/utils/services/db_probe.py`
- [ ] T7.2 Add a test asserting the CLI exits 0 when the DB driver is unavailable and when the module raises at import
- [ ] T7.3 Verify the deployed worker image tag is ≥ the Phase 2 merge SHA (`aws ecs describe-task-definition --task-definition palateful-worker-prod`)
- [ ] T7.4 Add the `healthCheck` block with `interval = 60` (E-4's budget, see Context) and `startPeriod` tuned to observed Celery boot time — files: `terraform/modules/ecs/main.tf`
- [ ] T7.5 Apply (Force Deploy if terraform-only); confirm `healthStatus` leaves `UNKNOWN` and reaches `HEALTHY` in <120s
- [ ] T7.6 Verify both fail-open legs (broken probe, non-auth DB error) and the true-positive leg with `DB_PASSWORD_SECRET_ARN` unset
- [ ] T7.7 Measure and record probe cost; write `evals/E-8_worker-healthcheck.md`

---

### 8. Phase: Deploy-freeze visibility (FR-6)

**Overview**: Make a silent three-month freeze impossible to repeat, on a
schedule and on demand. Last because it is the only phase that addresses the
*meta*-failure rather than the outage.

**Files**:
- `.github/workflows/deploy-freshness.yml` — **new**. `schedule: cron '0 15 * * *'`
  (09:00 MDT) plus `workflow_dispatch`. Checks out with `fetch-depth: 0`,
  configures the existing static AWS credentials, resolves the running task
  definition, extracts the tag, resolves `git log -1 --format=%ct <tag>`,
  and **fails the run** when the gap exceeds 7 days.
- `bin/prod-status` — add a deployed-image line with the tag and its age,
  reusing the `describe-services` call already at `:15-18`.
- `evals/E-7_deploy-freeze-visibility.md` — **new**, the E-7 record.

**Context**:
- **It must resolve the *running* task definition, not the family.**
  `deploy-services` uses the family shortcut
  (`--task-definition palateful-api-prod`, `ci.yml:867-885`), which returns
  the family's newest ACTIVE revision — correct *there*, because it runs
  right after `terraform-prod` wrote that revision. FR-6 asks the opposite
  question, so it must go `describe-services` → `services[0].taskDefinition`
  → `describe-task-definition` on that **revision ARN**. Using the family
  shortcut would report the newest task definition as "deployed" and mask
  exactly the freeze this check exists to catch. Reuse only the
  tag-extraction idiom (`containerDefinitions[0].image`, `tag="${image##*:}"`).
- **It must not set `environment: production`.** Every deploy-touching job
  does (`ci.yml:463`, `:706`, `:852`), which applies GitHub's
  required-reviewer gate — a scheduled job that waits for manual approval
  can never detect an unattended freeze. The exception is justified because
  the job is strictly read-only.
- **Accepted cost, stated plainly**: the check shares its fate with the CI
  system whose silent breakage it exists to catch. Mitigated only by living
  in a **separate workflow file with its own trigger**, so a red `ci.yml`
  does not skip it. This was the deciding argument against putting it inside
  `ci.yml` — a push-triggered job would have been skipped throughout this
  very incident.
- `fetch-depth: 0` is required: the deployed SHA may be months old (92 days
  when this workstream opened).
- UC-5 folds into `bin/prod-status` rather than a net-new script — one code
  path, one place an operator looks.

**Verification plan**:
- Type: human
- Success criteria (E-7):
  - `workflow_dispatch` run against current prod reports the true gap;
    cross-check against `bin/prod-status` and `git log`.
  - A synthetic >7-day gap **fails** the run; a <7-day gap passes.
  - The check reports the **running** revision — verify by confirming a
    newer ACTIVE task-definition revision does not change its answer.
  - The scheduled trigger fires unattended (confirm the next morning) with
    no approval prompt.
  - `bin/prod-status` prints the deployed tag and its age.
  - Gap reported within 24h of crossing 7 days.

**Tasks**:
- [ ] T8.1 Write `deploy-freshness.yml`; deliberately omit `environment: production` and comment why — files: `.github/workflows/deploy-freshness.yml`
- [ ] T8.2 Implement the running-revision lookup (`describe-services` → revision ARN → `describe-task-definition`); comment the family-shortcut trap
- [ ] T8.3 Verify with `workflow_dispatch` against current prod
- [ ] T8.4 Test both sides of the 7-day boundary
- [ ] T8.5 Add the deployed-image + age line to `bin/prod-status` — files: `bin/prod-status`
- [ ] T8.6 Confirm the scheduled run fires unattended
- [ ] T8.7 Write `evals/E-7_deploy-freeze-visibility.md`

---

### 9. Phase: Rotation drill — measure G-2, G-3, G-4

**Overview**: Force a rotation on purpose and measure what actually happens.
Every phase above proves a *mechanism* against mocks; this proves the
*outcome* against production. Without it, G-2 and G-3 stay inferences until
~2026-10 — and at a 90-day cadence a regression would surface late and
unattended.

**Two legs, deliberately.** The layers overlap, and a single drill with
everything enabled measures only the layer that wins:

- **Leg A — detection backstop.** `DB_PASSWORD_SECRET_ARN` **unset** on both
  services, so FR-5 is inert and FR-2 + FR-4 carry the recovery. This is the
  only way to get a real number for the detection path, whose worst-case
  arithmetic (`design.md:101-107`) lands near 4 minutes against G-2's
  5-minute budget "with little margin" — the open question Design
  explicitly deferred to "measurement at the first real rotation".
- **Leg B — steady state.** Variable set, all layers live. FR-5 should make
  the rotation a complete non-event; FR-4's redeploy fires anyway and is
  redundant-but-harmless; FR-2 should never trip. Record which layers
  actually engaged.

**Files**:
- `evals/E-drill-rotation.md` — **new**. Baseline, both legs' timelines,
  measured actuals for G-2 / G-3 / G-4, and what broke.
- No production code. Any fix this drill surfaces is filed as a
  `debug/debug-*.md` spec, not folded in here.

**Context**:
- **This is a deliberate production action against a single-operator
  system.** Run it attended, in a window you choose, with `bin/prod-status`
  and CloudWatch open. Strictly safer than discovering a broken self-heal
  path at 3am in October.
- **A short observation window produces a false pass.** Every engine sets
  `pool_recycle=3600` (`database.py:48`, `:96`, `:125`), and
  `terraform/modules/rds/main.tf:113-116` records the mechanism verbatim:
  the pool "masks the failure for hours/days while open connections stay
  authenticated, then 5xx's once the pool recycles." With FR-5 completely
  broken, a 30-minute attended watch still shows zero 5xx — the exact
  false-negative that produced the six-day outage. **A positive control is
  mandatory**: prove a *new* connection authenticated with the *new*
  password (assert `pg_stat_activity.backend_start` post-rotation, force
  pool turnover, or run the probe in-task), and observe for at least
  `pool_recycle` (3600s) before declaring Leg B a pass.
- **The drill triggers rotation manually** (`aws secretsmanager rotate-secret`),
  which is not the scheduled path that caused the incident
  (`rotate_immediately = false`, `rds/main.tf:203`). If the two emit
  different event shapes, the drill could green-light a rule that never
  fires in October. Record the drill's event JSON and compare it against the
  scheduled-rotation shape; if they cannot be compared, say so explicitly in
  the eval and let the armed outcome cover it.
- **UC-2's unattended property is not proven here.** The drill proves the
  mechanism with an operator watching; UC-2/G-3 are fully scored only at the
  armed outcome review against a natural rotation.
- Rollback: the existing circuit breaker (`ecs/main.tf:366-369`, `:468-471`)
  plus the known-good fallback — `DB_PASSWORD` is still in both task
  definitions, so unsetting `DB_PASSWORD_SECRET_ARN` and forcing a
  deployment restores today's behavior.

**Verification plan**:
- Type: human
- Success criteria:
  - **G-2 (Leg A)**: from CloudTrail `RotationSucceeded` to the last
    rotation-attributable 5xx is **under 5 minutes** on the detection path.
    This is the number Design deferred; it is the one with margin risk.
  - **G-2 (Leg B)**: steady-state 5xx window is ~0.
  - **Positive control (Leg B)**: a connection established *after*
    `RotationSucceeded` authenticated with the *new* password, proven from
    `pg_stat_activity` or an in-task probe — not inferred from absence of
    errors. Observation window ≥ 3600s.
  - **G-3**: **0** manual interventions **after the rotation trigger** —
    any state-changing action following T9.4 counts as an intervention and
    fails the criterion. (The trigger itself is the stimulus, not an
    intervention.)
  - **G-4**: the freshness workflow's reported gap matches `git log`. Note
    the absolute age is trivially small right after Phases 1–8 deploy; the
    real G-4 evidence is the armed outcome review, not this measurement.
  - Both ECS services reach a steady `RUNNING` state with `HEALTHY` status.
  - Every layer's engagement recorded, per leg, in `evals/E-drill-rotation.md`
    — including which layer won and which were redundant.
  - `devx outcome arm 462355` run with a measure-by date.

**Tasks**:
- [ ] T9.1 Capture the baseline: `bin/prod-status`, current 5xx rate, deployed tag + age, both services' `healthStatus`, and a `pg_stat_activity` snapshot
- [ ] T9.2 Confirm the rollback path — know the exact command to restore `DB_PASSWORD_SECRET_ARN` and force a deployment before starting
- [ ] T9.3 **Leg A**: unset `DB_PASSWORD_SECRET_ARN` on both services; rotate; time `RotationSucceeded` → healthy replacement against the 5-minute budget; record the detection-path number
- [ ] T9.4 **Leg B**: restore the variable; rotate again; record the timeline
- [ ] T9.5 Run the positive control and hold the observation ≥ `pool_recycle` (3600s) before calling Leg B a pass
- [ ] T9.6 Capture the drill's rotation event JSON; compare against the scheduled-rotation shape or record that it is unverified
- [ ] T9.7 Measure G-2, G-3, G-4; run `audit_errors.py --window 2h` to catch anything unattributed
- [ ] T9.8 Record actuals + per-leg layer engagement in `evals/E-drill-rotation.md`
- [ ] T9.9 File any surfaced defect as a `debug/debug-*.md` spec — do not fix in place
- [ ] T9.10 `devx outcome arm 462355 --measure-by <first natural rotation>`
