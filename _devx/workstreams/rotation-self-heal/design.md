# Design — Rotation Self Heal

<!-- Stage: Design. Gate: `devx gate coverage 462355` (design mode — one
     tri-state row per G-/UC-/CAP-/FR- ID in prd.md). Hard rule: don't plan
     here. No phases, no tasks — design is the approach, not the sequence. -->

## Overview

- **Objective**: make a routine credential rotation a non-event. Today a
  rotation silently breaks every database connection for as long as it
  takes a human to notice (six days, on 2026-07-21), because ECS resolves
  `DB_PASSWORD` from Secrets Manager at task start and the process never
  re-reads it. Underneath that sits a second failure: `main` has been
  un-deployable since 2026-04-26, so the fix that was already written
  (`e74303f`) never reached production.

- **Solution**: three independent layers, each of which alone shortens the
  outage, plus the deploy path that lets any of them ship.
  **(a) Detect** — `/v1/health` opens a *fresh* connection and returns 503
  **only** on a positively-identified authentication failure, so ECS
  replaces the task and the replacement picks up the current password.
  **(b) Preempt** — an EventBridge rule on the secret's `AWSCURRENT` label
  move forces a new deployment of api and worker before any request fails.
  **(c) Eliminate** — engines resolve the password at *connection* time
  from Secrets Manager with a TTL cache and one invalidate-and-retry on
  auth failure, so a rotation requires no restart at all. Layer (c) makes
  (a) and (b) redundant in the steady state; they stay as backstops for
  credential paths (c) does not cover and for the window before it lands.

## Constraints

- **`services/api` enforces 100% branch coverage** —
  `services/api/pyproject.toml:43` `fail_under = 100` (omits
  `src/manage.py`, `src/api/v1/user/create_user.py`). Every new line in the
  API needs a covering test or the local gate fails. `libraries/utils` sets
  **no** `fail_under` (`libraries/utils/pyproject.toml:5-7`,
  `[tool.coverage.report]`), which is why the credential machinery belongs
  there rather than in the API.
- **`libraries/utils` tests live in `libraries/utils/test/`** — singular,
  no `conftest.py`. The test target runs `poetry run pytest libraries/utils/`
  from the workspace root (`libraries/utils/project.json:28-34`), so it
  picks up the *root* pytest config (`pyproject.toml:68-70`,
  `asyncio_mode = "auto"`). Both E-5 and E-6 `Verified-by` paths already
  match this layout.
- **CI authenticates to AWS with static access keys**, not OIDC —
  `.github/workflows/ci.yml:671-675` and three siblings use
  `secrets.AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`. There is no
  role-to-assume to attach a narrower policy to.
- **Every deploy-touching job sets `environment: production`**
  (`ci.yml:8-10`), which applies GitHub's required-reviewer gate. A
  *scheduled* job that sets it would block on manual approval and never
  fire unattended — so FR-6 must be read-only and deliberately outside that
  convention.
- **The worker has no HTTP surface.** `services/worker/src/main.py` is 14
  lines of Celery; `services/worker/Dockerfile:99,135` has no `EXPOSE` and
  no `HEALTHCHECK`; `pyproject.toml` carries no fastapi/uvicorn. Any worker
  health check must be a `CMD-SHELL` probe, not an HTTP endpoint.
- **EventBridge cannot call `ecs:UpdateService` directly.** Its native ECS
  target is `RunTask`, which launches a one-off task and cannot force a
  service deployment. A compute target is structurally required.
- **No Lambda, EventBridge, or scheduled-job pattern exists in this repo.**
  Verified: zero `aws_lambda_function`, `aws_cloudwatch_event_rule`, or
  `data "archive_file"` across `terraform/`; no `archive` provider in any
  lockfile; the only `schedule:` in `.github/workflows/` is a deliberate
  never-fires sentinel (`devx-promotion.yml:7-12`, `cron: "0 0 31 2 *"`).
  This workstream establishes both patterns.
- **Both ECS services run a deployment circuit breaker with rollback**
  (`terraform/modules/ecs/main.tf:366-369`, `:468-471`). A forced
  deployment whose tasks fail to become healthy rolls back automatically.
- **Existing detection surfaces are already wired** — the api container
  health check (`ecs/main.tf:318-324`, `urllib.request.urlopen` on
  `/v1/health`, interval 30 / timeout 5 / retries 3 / startPeriod 60)
  raises on a 503, and the ALB target group
  (`terraform/modules/alb/main.tf:58-71`) matches `200` with interval 60 /
  unhealthy_threshold 3. Neither needs new plumbing; they need the endpoint
  underneath them to tell the truth.
- **Prod image tag is the full commit SHA** (`ci.yml:655`
  `IMAGE_TAG: ${{ github.sha }}`, passthrough at `:616-633`). "What is
  deployed" is answerable only by querying AWS — no manifest is committed.

## Risks

- **A misclassified transient failure replaces every task at once.** All
  tasks share one database; if the probe returns 503 for an RDS failover or
  a network blip, ECS drains the entire service and converts a 30-second
  blip into a full outage — strictly worse than doing nothing. → Probe is
  **fail-open**: 503 only when the error is positively identified as
  SQLSTATE `28P01`/`28000`; every other exception, including an unhandled
  one, returns 200. → proven by **E-3**
- **This risk is live on `main` today.** `services/api/src/routers/v1/health_router.py:25-27`
  currently catches bare `Exception` and raises 503 for *any* database
  error. That code is on `main` and undeployed; shipping FR-1 without FR-2
  would deploy the mass-replacement hazard. → FR-2 must land in the same
  deploy as, or before, the first successful `deploy-services`. → proven by
  **E-3**
- **Probe traffic opens a TLS handshake per health check.** Two independent
  checkers (container 30s, ALB 60s) against a fresh-connection probe is
  ~3 new connections/minute/task, permanently. → dedicated `NullPool`
  engine behind a TTL-cached verdict, ≤1 fresh connection per 60s window.
  → proven by **E-4**
- **Detection latency may exceed G-2's 5-minute budget.** Worst case
  stacks: verdict TTL (≤60s) + 3 consecutive container failures at 30s
  (~90s) + task stop/start with `startPeriod` 60s ≈ **4 minutes**. That
  fits, but with little margin, and the TTL and the retry count trade
  directly against E-4. → TTL is configurable rather than hardcoded, and
  FR-4 preempts detection entirely by redeploying at rotation time rather
  than waiting for failures. → proven by **E-2**, **E-5**
- **A bug in connect-time resolution breaks 100% of connections**, not just
  post-rotation ones — a far larger blast radius than the failure being
  fixed. → the entire path is gated on `DB_PASSWORD_SECRET_ARN` being set;
  absent, no listener is registered and no Secrets Manager client is
  constructed, so behavior is byte-identical to today. Rollback is removing
  one environment variable. → proven by **E-6**
- **Secrets Manager becomes a hard dependency of every new connection.** A
  throttle or outage there would break connections that would otherwise
  have succeeded. → TTL cache (default 300s) means steady-state traffic
  makes no API calls at all, and `DB_PASSWORD` stays in the task definition
  as the fallback the provider falls back to when resolution raises.
  → proven by **E-6**
- **`libraries/agent` builds its own engines** — `agent/tasks.py:28-37` and
  `agent/runner.py:25-35` each call `create_engine(settings.database_url,
  pool_pre_ping=True)` independently of
  `utils/services/database.py`. A fix applied only to the utils engines
  leaves the worker's agent tasks still failing after a rotation. → the
  registration helper is applied at **every** engine construction site, and
  the site list is part of the design's Architecture section below.
  → proven by **E-6**
- **The exact EventBridge event shape is unverified.** The PRD names the
  native Secrets Manager "Secret Label Updated" event; the field names and
  `detail-type` string have not been confirmed against a live event. A
  wrong pattern means the rule silently never fires — the same class of
  silent failure this workstream exists to remove. → verified at RED
  against a recorded event, with the CloudTrail `RotationSucceeded` signal
  (observed in this incident at 2026-07-21T21:29:14) as the proven
  fallback. → proven by **E-5**
- **The Flutter date fuse is not limited to the three failing tests.**
  `app/lib/features/activity/imports_tab.dart:168` filters `completed` and
  `skipped` items older than 30 days against `DateTime.now()`, and 39 test
  files under `app/test/` carry hardcoded `2026-0*` literals. Fixing three
  assertions unblocks the deploy today and leaves the mechanism intact to
  re-freeze it later. → FR-1 fixes the blockers; the repo-wide sweep is
  named in Out of scope and filed separately. → proven by **E-1**

## Trade-offs

- **Fail-open over fail-closed on the health probe.** A false 503 costs a
  full outage across every task; a false 200 costs exactly the status quo.
  The asymmetry is severe enough that unclassified exceptions return 200,
  accepting that a novel credential-failure mode would go undetected by
  layer (a) rather than risking self-inflicted mass replacement.
- **Ship restart-based recovery before eliminating restarts.** FR-5 is the
  better answer and makes FR-2/FR-4 redundant, but it touches every
  connection path in the codebase. FR-2 and FR-4 are additive, independently
  reversible, and land inside the deadline; FR-5 lands after, with time to
  test.
- **A ~20-line Lambda over Step Functions or an SSM Automation runbook.**
  The task is one boto3 call per service. A Lambda is the smallest thing
  that can hold it, needs no new service concept, and its handler is
  directly unit-testable with a stubbed client.
- **Scheduled GitHub Action over a CloudWatch alarm for FR-6** (locked with
  the user). No new AWS surface for a single number, and the check is
  testable locally. Accepted cost: the freshness check shares its fate with
  the CI system whose silent breakage it exists to catch — a CI outage
  hides both. Mitigated only by the check being a separate workflow file
  with its own trigger, so a red `ci.yml` does not skip it.
- **`CMD-SHELL` database probe over an HTTP listener for the worker.**
  Adding fastapi/uvicorn to a Celery-only image to serve one health route
  is a heavier change than invoking the same probe module as a CLI, and it
  reuses FR-2's classification logic rather than restating it.
- **Keep `DB_PASSWORD` in the task definitions after FR-5.** It is
  redundant once connect-time resolution works, but retaining it preserves
  a working fallback if Secrets Manager is unreachable at connect time, and
  makes the FR-5 rollout reversible by unsetting one variable. Removing it
  is a candidate for the Outcome review, not for this workstream.

## Out of scope

- **The repo-wide hardcoded-date sweep in Flutter tests.** 39 files carry
  `2026-0*` literals on the same 30-day fuse as the three blocking tests.
  FR-1 covers only what blocks the deploy graph; the sweep is a separate
  test-hygiene item.
- **`services/migrator` credential resolution.** The migrator is a
  short-lived one-off task (`ecs/main.tf:482-532`) that resolves
  `DB_PASSWORD` at start and exits — start-time resolution is correct for
  it. Its task role also carries zero policies today
  (`iam/main.tf:572-592`), so including it would mean net-new IAM for no
  benefit.
- **RDS IAM database authentication.** It eliminates passwords entirely,
  but requires database user changes, a 15-minute token lifetime, and does
  not cover the master-password path the migrator uses. Larger blast
  radius than FR-5 for the same failure mode.
- **The Flutter client's error surface.** `login_screen.dart:96` swallowing
  a 500 delayed the report by days; it did not cause the outage. Named as
  a non-goal in the PRD and untouched here.
- **Hardening the parser image build.** `services/parser/Dockerfile.batch`
  has several unpinned network dependencies (deadsnakes PPA, `get-pip.py`,
  unpinned Poetry, a build-time HuggingFace model download, a hand-rolled
  torchvision shim). FR-1 confirms whether the 2026-05-03 failure still
  reproduces; making that build robust is its own workstream.
- **General Celery liveness for the worker.** FR-3 gives the worker a
  health-check mechanism where it had none, scoped to the credential
  failure this workstream is about. A wedged consumer or a lost broker
  connection remains undetected; a heartbeat or broker-ping probe is a
  separate item.
- **General CI health.** Only the jobs gating `deploy-services` and
  `deploy-web` are in scope.

## Assumptions

Each is a revision trigger if it breaks.

- **The 2026-05-03 `deploy-images (parser)` and `deploy-web` failures no
  longer reproduce.** Nothing in the repo proves either way; the first
  green `flutter-test` run on `main` resolves it empirically. If they do
  reproduce, FR-1 grows to include them and G-1's 2026-07-29 date is at
  risk.
- **Rotation cadence moves to 90 days.** Locked with the user this stage:
  the pending `aws_secretsmanager_secret_rotation.db_master` from
  `e74303f` (`terraform/modules/rds/main.tf:201-208`,
  `master_password_rotation_days` default 90 at `:105-118`) is allowed to
  apply. This **contradicts the PRD's stated non-goal** ("changing the
  rotation cadence") and requires `devx revise` on the PRD before the Plan
  gate. Consequence: after the first successful `terraform-prod`, the next
  rotation moves from 2026-07-29 to roughly 2026-10, the 07-29 deadline
  pressure disappears, and the self-heal path is exercised ~4×/year instead
  of weekly — so its regressions will be found late unless the RED
  artifacts stand in for real rotations.
- **A replacement task gets the current password.** ECS resolves
  `valueFrom` at task start (`ecs/main.tf:306`, `:426`), so a task started
  after the rotation authenticates successfully. This is what makes layers
  (a) and (b) work at all; if it were false, only FR-5 would help.
- **Prod is reachable from a GitHub-hosted runner with the existing keys**
  for read-only `ecs:DescribeServices` / `ecs:DescribeTaskDefinition`.
- **`git log` can resolve the deployed SHA.** FR-6 compares the deployed
  image tag (a full commit SHA) against `main`; the workflow must check out
  with `fetch-depth: 0` because the deployed SHA may be months old.
- **Secrets Manager stores the password under the JSON key `password`** —
  consistent with the `valueFrom` selector `"${var.db_master_secret_arn}:password::"`
  already in use at `ecs/main.tf:306`.

## Discarded considerations

- **Shorten `pool_recycle` to force reconnects.** Reconnects would present
  the same stale in-process password. `pool_pre_ping` has the same problem
  — it validates an already-authenticated connection and never re-
  authenticates.
- **EventBridge → ECS `RunTask` directly, skipping Lambda.** `RunTask`
  launches a standalone task; it cannot force a deployment of a running
  service. Structurally unable to do the job.
- **A sidecar container that restarts the app on rotation.** ECS replaces
  tasks rather than restarting processes inside them, so the sidecar would
  have to kill its peer and rely on the task failing — strictly more moving
  parts than forcing a deployment from outside.
- **Writing the password to a file that a sidecar refreshes, read per
  connection.** Solves the same problem as FR-5 with an extra container, a
  shared volume, and a file-watch race.
- **A custom Secrets Manager rotation Lambda.** Replacing RDS-managed
  rotation with our own would let us orchestrate the redeploy inside it,
  but takes ownership of a security control that currently works correctly.
  The failure is in how the application consumes the secret, not in how it
  is rotated.
- **Making `/v1/health` fail-closed and relying on the ECS circuit breaker
  to catch mistakes.** The circuit breaker rolls back a *deployment*; it
  does not protect against healthy-task replacement driven by a health
  check on an unchanged task definition.

## Wrap, don't duplicate

- **Reuses**:
  - `services/api/src/routers/v1/health_router.py:15-28` — the endpoint and
    its route registration (`routers/v1_router.py:29,36`) already exist and
    are already probed by both checkers. FR-2 changes what the handler
    decides, not where it lives.
  - `terraform/modules/ecs/main.tf:318-324` — the api container health
    check is already wired and already fails on a 503. No Terraform change
    is needed for FR-2's detection path.
  - `terraform/modules/alb/main.tf:58-71` — ALB health check, unchanged.
  - `terraform/modules/iam/main.tf:362-378` — the execution role's
    `secretsmanager:GetSecretValue` policy is the exact shape FR-5 copies
    onto the api and worker **task** roles (`:416`, `:519`).
  - `libraries/utils/utils/services/aws.py:6-7,36-37` — the established
    home for boto3 clients (`s3`, `batch`); the Secrets Manager client
    joins it rather than starting a new convention. `boto3` is already a
    declared dependency at `libraries/utils/pyproject.toml:35`.
  - `libraries/utils/utils/constants.py:19-42` — `_build_database_url()`
    stays the single place URLs are composed; FR-5 overrides only the
    password at connect time and does not fork URL assembly.
  - `libraries/utils/test/test_db_pool_constants.py` — the established
    `monkeypatch.setenv` + `importlib.reload` pattern for testing
    env-derived module state; the FR-5 tests follow it.
  - `.github/workflows/ci.yml:867-885` — `deploy-services`'s image-tag
    extraction idiom (`containerDefinitions[0].image` → `tag="${image##*:}"`).
    FR-6 reuses the extraction but not the family-name lookup, for the
    reason given in Architecture §5.
  - `aws ecs update-service --force-new-deployment` (`ci.yml:902`) — the
    action FR-4's Lambda performs is the one `deploy-services` already
    performs; the Lambda is a second trigger for a proven operation.
  - `bin/prod-status:15-18` — already runs `describe-services` against both
    prod services. FR-6's on-demand half (UC-5) extends it with a deployed-
    image-age line rather than adding a second operator script.

- **Adds**:
  - `libraries/utils/utils/services/db_credentials.py` — SQLSTATE
    classification, the TTL-cached Secrets Manager password provider, and
    the engine registration helper. Genuinely new: nothing in the repo
    reads Secrets Manager from Python today (verified: zero
    `secretsmanager` hits across `services/`, `libraries/`, `tools/`,
    `scripts/`).
  - `libraries/utils/utils/services/db_probe.py` — fresh-connection probe
    with a TTL-cached verdict, in async (API) and sync (worker CLI) forms.
  - `libraries/utils/utils/services/rotation_redeploy.py` — the Lambda
    handler. Deliberately stdlib + boto3 only, so it zips as a single file.
  - `terraform/modules/rotation-redeploy/` — the first EventBridge rule and
    the first Lambda in this repo.
  - `.github/workflows/deploy-freshness.yml` — the first working scheduled
    workflow in this repo.

## Design

### Architecture

Four surfaces, in dependency order.

**1. Deploy path (FR-1 → CAP-1).** `flutter-test` is a root job with no
`needs:` (`ci.yml:304`) but sits in the `needs:` list of both `deploy-web`
(`ci.yml:462`) and `detect-changes` (`ci.yml:521`), so its 3 failures skip
every deploy job. The failures are a date time-bomb, not a regression:
`app/lib/features/activity/imports_tab.dart:168` computes
`DateTime.now().subtract(const Duration(days: 30))` and applies it to
`completed` (`:183-189`) and `skipped` (`:190-195`) items, while every
fixture in `imports_tab_test.dart` hardcodes a `2026-04-18T10:*` timestamp
(22 `created_at` occurrences; the three failing tests are the `testWidgets`
at `:211`, `:425`, `:462`, whose `completed`/`skipped` fixtures sit at
`:277`, `:445`, and `:510-525`) — 100 days old as of today, so every
`completed` fixture is filtered out. The cutoff is intentional product behavior
(commented at `imports_tab.dart:165-167`); **the fix belongs in the test**,
making fixture timestamps relative to `DateTime.now()`. Note a fourth,
latent assertion at `imports_tab_test.dart:544`
(`find.textContaining('Skipped · 1')`) on the same fuse, currently masked
because `:542` aborts first — E-1's "0 failures" threshold covers it.

**2. Credential-aware detection (FR-2, FR-3 → CAP-2, CAP-3).**

A new module `libraries/utils/utils/services/db_probe.py` owns the probe.
It builds a dedicated engine with `poolclass=NullPool` — so every probe is
a genuinely new connection and TLS handshake, which is the whole point —
and wraps it in a TTL-cached verdict so the handshake happens at most once
per window regardless of how often the two checkers ask.

Classification lives in `db_credentials.is_auth_error(exc)`, which unwraps
SQLAlchemy's `OperationalError` to its `.orig` and matches
`sqlstate`/`pgcode` against `{"28P01", "28000"}` — covering both the
asyncpg (`InvalidPasswordError`, `InvalidAuthorizationSpecificationError`)
and psycopg2 shapes. The verdict is a three-state value: `ok`,
`auth_failed`, `other_error`.

`health_router.health_check` becomes: read the cached verdict; return 503
**only** on `auth_failed`; return 200 for `ok` **and** for `other_error`.
It no longer depends on `get_async_database` — a pooled connection cannot
observe the failure, since existing connections stay authenticated after a
rotation. The existing container health check
(`ecs/main.tf:318-324`) already turns that 503 into a task replacement, and
the replacement resolves the current password at start.

The worker (FR-3) has no HTTP surface, so it gets the same logic as a
module CLI: `python -m utils.services.db_probe` exits non-zero only on
`auth_failed`, wired as a `CMD-SHELL` `healthCheck` block on the worker
container definition (`ecs/main.tf:396-444`, which has none today —
`healthStatus: UNKNOWN`). `startPeriod` covers Celery boot.

Be precise about what this buys. FR-3's motivation is that the worker has
**no** health-check mechanism at all, so ECS cannot replace it under any
failure mode; this establishes the mechanism and removes `UNKNOWN`, which
is what E-8 measures. It does not make the worker's *liveness* observable
in general — a Celery consumer wedged on a poisoned task, or one that lost
its broker connection, still holds valid credentials and still reports
`HEALTHY`. Closing that needs a broker-level or heartbeat-based probe,
which is a different concern from credential rotation and is named in Out
of scope.

**3. Rotation-triggered redeployment (FR-4 → CAP-4).** A new Terraform
module `terraform/modules/rotation-redeploy/` defines an
`aws_cloudwatch_event_rule` whose pattern is scoped to the RDS-managed
secret ARN (`module.rds.db_master_secret_arn`, `rds/main.tf:235-238`) and
the `AWSCURRENT` label move, targeting an `aws_lambda_function` packaged
from a single file via `data "archive_file"` (`source_file`, so the zip
contains exactly `rotation_redeploy.py`; boto3 comes from the Lambda
runtime). The handler re-validates the event, then calls
`update_service(cluster, service, forceNewDeployment=True)` once per
service, aggregating failures so a partial failure is visible rather than
swallowed. Its execution role gets `ecs:UpdateService` +
`ecs:DescribeServices` on the two service ARNs, plus CloudWatch Logs.

Because the handler must zip as one file, `rotation_redeploy.py` imports
**only** stdlib and boto3 — no `utils` internals — even though it lives
inside the `utils` package (which is where E-5's agreed `Verified-by` path,
`libraries/utils/test/test_rotation_redeploy_handler.py`, expects it).

**4. Connect-time credential resolution (FR-5 → CAP-5, CAP-6).**

`db_credentials.py` provides a `SecretPasswordProvider` — a TTL-cached
(default 300s) reader over `boto3.client("secretsmanager")`, parsing the
`password` key from the secret JSON — and a registration helper that
attaches SQLAlchemy's `do_connect` event to an engine:

```
do_connect(dialect, conn_rec, cargs, cparams):
    cparams["password"] = provider.current()
    try:
        return dialect.connect(*cargs, **cparams)
    except Exception as exc:
        if not is_auth_error(exc):
            raise
        provider.invalidate()                  # exactly one invalidation
        cparams["password"] = provider.current()
        return dialect.connect(*cargs, **cparams)   # exactly one retry
```

Returning a connection from `do_connect` suppresses SQLAlchemy's own
connect, which is what makes the single retry expressible here rather than
in every caller. For async engines the listener attaches to
`engine.sync_engine`.

`resolve_password_provider()` returns `None` when `DB_PASSWORD_SECRET_ARN`
is unset, and the registration helper is then a no-op that constructs no
boto3 client and registers no listener — the byte-identical path E-6
requires for local, docker-compose, and CI (CAP-6).

Registration is applied at **every** engine construction site, which the
research enumerated:

| Site | Engine |
|---|---|
| `libraries/utils/utils/services/database.py:42-57` | sync `db_engine` |
| `libraries/utils/utils/services/database.py:60-105` | `async_db_engine` (via `sync_engine`) |
| `libraries/utils/utils/services/database.py:120-132` | `error_log_engine` |
| `libraries/agent/agent/tasks.py:28-37` | agent task engine |
| `libraries/agent/agent/runner.py:25-35` | agent runner engine |

The last two are the easy miss: `libraries/agent` builds its own engines
independently of `utils`, so a fix confined to `database.py` would leave
the worker's agent tasks broken after a rotation.

Note that FR-5 does **not** touch `constants.py:19-42`. The composed
`DATABASE_URL` still carries the task-start password; the listener
overrides `cparams["password"]` per connection. That keeps URL assembly in
one place and keeps the env-var value as the fallback the provider returns
to if resolution raises.

**5. Deploy-freeze visibility (FR-6 → CAP-1 support, G-4, UC-5).** A new
`.github/workflows/deploy-freshness.yml` on `schedule: cron '0 15 * * *'`
(09:00 MDT) plus `workflow_dispatch`. It checks out with `fetch-depth: 0`
(the deployed SHA may be months old), configures the existing static AWS
credentials, resolves the **running** task definition, extracts the tag,
resolves `git log -1 --format=%ct <tag>`, and fails the run when the gap
exceeds 7 days. A failing scheduled run is what notifies the operator.

The tag extraction borrows `deploy-services`'s idiom (`ci.yml:867-885`,
`describe-task-definition ... containerDefinitions[0].image` then
`tag="${image##*:}"`) but **must not** copy its lookup. That job passes the
task-def *family* name (`--task-definition palateful-api-prod`), which
returns the family's latest ACTIVE revision — correct there, because it
runs immediately after `terraform-prod` wrote that revision and is checking
what is about to be deployed. FR-6 asks the opposite question — what is
actually running — so it must go `describe-services` → `services[0].taskDefinition`
(the revision ARN the service is on) → `describe-task-definition` on that
ARN. Using the family shortcut would report the newest task definition as
"deployed" and mask exactly the freeze this check exists to catch.

It deliberately does **not** set `environment: production`: that would
apply the required-reviewer gate (`ci.yml:8-10`) and a check that waits for
manual approval cannot detect an unattended freeze. The justification for
the exception is that the job is strictly read-only.

UC-5 (operator can tell, quickly, what is deployed and how stale) is served
by extending the existing `bin/prod-status` rather than adding a script.
That script already runs `aws ecs describe-services --cluster palateful-prod
--services palateful-api-prod palateful-worker-prod` (`bin/prod-status:15-18`)
— the exact call the freshness check needs — so it gains a deployed-image
line with the tag and its age. One code path, one place an operator looks,
and no second on-demand surface to keep in sync with the workflow.

### Interfaces

`libraries/utils/utils/services/db_credentials.py`

| Symbol | Signature | Behavior |
|---|---|---|
| `is_auth_error` | `(exc: BaseException) -> bool` | Unwraps `.orig` / `__cause__`; `True` iff SQLSTATE ∈ `{28P01, 28000}` |
| `SecretPasswordProvider` | `(secret_arn: str, ttl_s: int = 300, client=None)` | TTL cache over `get_secret_value`, reads JSON key `password` |
| `SecretPasswordProvider.current` | `() -> str` | Cached value; refetches past TTL; falls back to `DB_PASSWORD` on resolution error |
| `SecretPasswordProvider.invalidate` | `() -> None` | Drops the cached value so the next `current()` refetches |
| `resolve_password_provider` | `() -> SecretPasswordProvider \| None` | `None` when `DB_PASSWORD_SECRET_ARN` is unset |
| `register_rotating_credentials` | `(engine) -> bool` | Attaches `do_connect`; returns `False` and does nothing when no provider |

`libraries/utils/utils/services/db_probe.py`

| Symbol | Signature | Behavior |
|---|---|---|
| `ProbeVerdict` | enum | `OK` \| `AUTH_FAILED` \| `OTHER_ERROR` |
| `probe_async` | `() -> ProbeVerdict` | Fresh `NullPool` connection, `SELECT 1` |
| `probe_sync` | `() -> ProbeVerdict` | Same, sync driver, for the worker CLI |
| `cached_verdict_async` | `(ttl_s: int = 60) -> ProbeVerdict` | Serves cached verdict inside the window |
| `__main__` | CLI | Exit `0` unless `AUTH_FAILED` (exit `1`) |

`GET /v1/health` — unchanged path and 200 shape; adds a `db` field carrying
the verdict name. Returns **503** with `{"detail": "db credentials invalid"}`
only on `AUTH_FAILED`.

`libraries/utils/utils/services/rotation_redeploy.py`

| Symbol | Signature | Behavior |
|---|---|---|
| `handler` | `(event, context) -> dict` | Validates the event targets the configured secret; `update_service(..., forceNewDeployment=True)` once per service; returns `{"redeployed": [...], "failed": [...]}`; non-zero/error result on partial failure; **0 calls** on a non-matching secret |

Configuration (all new environment variables):

| Variable | Consumer | Absent behavior |
|---|---|---|
| `DB_PASSWORD_SECRET_ARN` | api, worker | No provider, no listener, no boto3 client — today's behavior exactly |
| `DB_PROBE_TTL_S` | api, worker | Defaults to 60 |
| `DB_SECRET_TTL_S` | api, worker | Defaults to 300 |
| `ECS_CLUSTER`, `ECS_SERVICES`, `WATCHED_SECRET_ARN` | Lambda | Required; handler errors |

### Data

No schema changes, no migrations, no new stores. All state is in-process
and ephemeral: the probe's cached verdict (a value plus a timestamp) and
the provider's cached password (likewise), both per-process and lost on
restart — which is correct, since a restart re-resolves anyway. The secret
itself is RDS-managed and already exists
(`terraform/modules/rds/main.tf:148` `manage_master_user_password = true`);
this design reads it, never writes it. The cached password is held only in
memory, never logged, and never written to disk; existing log redaction
(`devx.config.yaml → observability.redact`) covers the surrounding fields.

## Migration plan

Ordered by the deadline shape locked with the user: CI, health probe, and
EventBridge before the 2026-07-29 rotation; the rest after.

1. **Unblock the deploy path.** Fix the Flutter fixtures so `flutter-test`
   reports 0 failures. Push to `main`, watch the full graph — this is also
   the empirical answer to whether the 2026-05-03 `deploy-web` and
   `deploy-images (parser)` failures still reproduce. Nothing else can ship
   until this is green.
2. **Land FR-2 before or with the first `deploy-services`.** The bare-
   `except` 503 currently on `main` is a mass-replacement hazard; the first
   successful deploy must not carry it un-fixed.
3. **Apply FR-4's Terraform.** This is the first `terraform apply` since
   2026-04-26, so it also lands every other pending Terraform change —
   including the 90-day rotation cadence from `e74303f`. Review the plan
   output before applying rather than trusting the diff to be limited to
   this workstream.
4. **Verify at the next real rotation**, then land FR-5 behind an unset
   `DB_PASSWORD_SECRET_ARN`. Merging it is a no-op until the variable is
   set on a task definition; enable it on the worker first (lower user
   impact than the API), confirm, then the API.
5. **FR-3 and FR-6** last — neither is on the outage path.

Rollback at each step is removal, not repair: FR-5 unsets one environment
variable, FR-4 disables one EventBridge rule, FR-2 is a single handler
revert, FR-3 removes a `healthCheck` block.

## Resolved design questions

- **Where does FR-6's freshness check live?** → A scheduled GitHub Action
  (`deploy-freshness.yml`, daily 15:00 UTC) rather than a CloudWatch alarm
  or a job inside `ci.yml`. Decided with the user this stage. A job inside
  `ci.yml` was rejected for the reason it would have failed in this very
  incident: it only runs on push, and a red CI meant it would have been
  skipped.
- **What must be true before 2026-07-29?** → CI green (FR-1), the
  credential-aware health probe (FR-2), and rotation-triggered redeployment
  (FR-4). FR-3, FR-5, FR-6 land after. Decided with the user this stage.
- **What happens to the pending 90-day rotation cadence?** → It is allowed
  to apply, as `e74303f` intended. Decided with the user this stage. This
  contradicts the PRD's non-goal and requires `devx revise` on the PRD
  before the Plan gate — recorded in Assumptions with its consequences.
- **Does the health probe need a pooled or fresh connection?** → Fresh.
  Existing pooled connections remain authenticated across a rotation, so a
  pooled probe cannot observe the failure at all — which is why the
  currently-undeployed probe in `health_router.py:24` would not have caught
  this incident even if it had shipped.
- **Where does the Lambda handler live?** → `libraries/utils/utils/services/`,
  matching E-5's agreed `Verified-by` path, with a hard constraint that it
  import only stdlib and boto3 so `archive_file` can package it as a single
  file.
- **Sync or async probe?** → Both, sharing one classifier. The API is async
  and the worker has no async entrypoint for a `CMD-SHELL` probe; the
  business logic (SQLSTATE classification) is shared, only the driver call
  differs.

## Unresolved design questions

- **The exact `detail-type` and `detail` field names of the Secrets Manager
  "Secret Label Updated" event.** Resolved at RED by matching against a
  recorded event before the rule is trusted; the CloudTrail
  `RotationSucceeded` signal observed in this incident is the fallback
  pattern. Blocks E-5 (P0) if neither pattern can be confirmed.
- **Whether `DB_PROBE_TTL_S = 60` leaves enough margin under G-2.** The
  worst-case arithmetic lands near 4 minutes against a 5-minute budget. The
  TTL trades directly against E-4's ≤1-connection-per-60s threshold, so
  tightening one loosens the other. Resolved by measurement at the first
  real rotation; does not block a gate — FR-4 makes the detection path a
  backstop rather than the primary mechanism.
- **Whether `deploy-web`'s unpinned `flutter-version` and `wrangler@latest`
  (`ci.yml:466-469`, `:493`) are the 2026-05-03 failure cause.** Resolved
  empirically by step 1 of the migration plan. If they are, pinning both
  falls inside FR-1; if not, they stay as noted hazards.
