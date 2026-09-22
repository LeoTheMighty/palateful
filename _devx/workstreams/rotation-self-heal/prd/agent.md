# PRD — Rotation Self Heal

<!-- Stage: PRD. Gate: `devx gate prd 462355`. Every concrete item gets a
     stable ID (G-/UC-/CAP-/FR-). IDs are never renumbered. Traceability is
     by ID, not by prose. -->

## Problem

On 2026-07-21 21:29 MDT the RDS-managed master password rotated on its
routine 7-day schedule. ECS resolves `DB_PASSWORD` from Secrets Manager
**at task start** and bakes it into the container environment, so the
API and worker tasks — started 2026-07-16 and 2026-07-15 — kept
presenting the pre-rotation password. Every new database connection
failed with `FATAL: password authentication failed for user
"palateful"`. The outage ran **six days** and was found only because a
user tried to log in and got "Failed to fetch user data"
(`app/lib/features/auth/login_screen.dart:96` swallowing a 500 from
`GET /v1/users/me`).

Nothing detected it. The container and ALB health checks both hit
`/v1/health`, which returned 200 throughout, so ECS never replaced the
tasks. A DB probe that *would* have caught this was written on
2026-05-03 (`e74303f`, "db probe in /v1/health") and has been sitting
undeployed ever since: prod runs image `c85e350` from **2026-04-26**,
whose `/v1/health` is the trivial `return {"status": "ok"}`.

The reason it is undeployed is the deeper problem. CI on `main` has
been red continuously since 2026-04-26 — the last green run. Deploy
jobs in `.github/workflows/ci.yml` declare `needs: [setup, lint, test,
check-models, flutter-test, terraform]`, so a single failing job skips
every deploy step. The May 3 runs failed in `deploy-web` and
`deploy-images (parser)`; the current runs fail in `flutter-test` (3
tests in `app/test/features/activity/imports_tab_test.dart`, 1521
passing). Production has been un-deployable for three months, and no
signal surfaced that fact.

Rotation recurs every 7 days. The next one is **2026-07-29** — two days
out — so the same outage is scheduled to happen again unless the
credential path stops depending on task start time.

## Goals

- **G-1**: CI green on `main` with a completed prod deploy of current
  `main`, by **2026-07-29** (before the next scheduled rotation).
- **G-2**: API 5xx attributable to credential rotation drops from
  ~6 days to **under 5 minutes** per rotation event, measured at the
  2026-07-29 rotation and each subsequent one.
- **G-3**: **Zero** manual interventions per rotation event from
  **2026-08-01** onward (current: 1 unplanned intervention, at
  unbounded latency).
- **G-4**: Deployed prod image is **under 7 days behind `main`** at any
  check, sampled weekly from **2026-08-01** (current: 92 days).

## Non-goals

- **Designing a rotation cadence.** The system must tolerate rotation at
  whatever cadence is configured; rotating less often is not a fix and is
  not what this workstream builds.

  Revised at Design (2026-07-27). This bullet originally read "Changing the
  rotation cadence" and put the 7-day cadence out of scope entirely. That
  turned out to be unholdable: commit `e74303f` (2026-05-03) already
  authored `aws_secretsmanager_secret_rotation.db_master` with
  `master_password_rotation_days = 90`
  (`terraform/modules/rds/main.tf:105-118`, `:201-208`), undeployed only
  because `main` has been un-deployable since 2026-04-26. FR-4 requires a
  `terraform apply`, which necessarily lands that pending change too — so
  "leave the cadence alone" was never an available option, merely an
  unstated one. Decided with the user at Design: **let the 90-day cadence
  apply, as `e74303f` intended.**

  Consequences, recorded so they are not rediscovered: the next rotation
  moves from 2026-07-29 to roughly 2026-10; the two-day deadline pressure
  behind G-1 disappears; and the self-heal path is exercised ~4×/year
  rather than weekly, so its regressions will surface late unless the RED
  artifacts stand in for real rotations. G-2's and G-3's measurement dates
  are affected — see Design § Assumptions.
- **Reworking the Flutter error surface.** `login_screen.dart:96`
  swallowing the error into a `debugPrint` is a real diagnosability gap,
  but it is a client-side concern tracked separately — it did not cause
  the outage, only delayed the report.
- **General CI health.** Phase 1 unblocks the specific jobs blocking
  deploys. A broader "keep CI green" effort is out of scope.
- **Multi-region or failover work.** Unrelated to this failure mode.

## Users

- **Primary**: the single operator (Leo) running Palateful production —
  deploys, incident response, and on-call are all one person.
- **Secondary**: end users of the app, who experience the failure as a
  login that silently does nothing.
- **Anti-persona**: a multi-team org with a dedicated platform group and
  a staged rollout process. The design assumes one operator, no
  approval chain beyond GitHub environments, and no 24/7 attention.

## Use cases

- **UC-1**: Operator merges to `main` and the change reaches production
  without manual steps or a silent freeze.
- **UC-2**: A scheduled credential rotation occurs while nobody is
  watching, and the system restores itself with no human action.
- **UC-3**: A task holding unusable credentials is detected and replaced
  automatically, rather than serving 5xx indefinitely while reporting
  healthy.
- **UC-4**: A transient database outage (RDS failover, network blip)
  does **not** cause task churn — restarting cannot fix connectivity,
  so tasks must ride it out.
- **UC-5**: Operator investigating an incident can tell, quickly, which
  image is deployed and how far behind `main` it is.

## Capabilities

- **CAP-1**: CI on `main` completes green so its deploy jobs execute.
- **CAP-2**: The API health check distinguishes a credential failure
  (restart fixes it) from a transient DB failure (restart does not).
- **CAP-3**: ECS replaces tasks whose database credentials are
  unusable, without operator action.
- **CAP-4**: A credential-rotation event proactively triggers
  redeployment of both api and worker.
- **CAP-5**: Services resolve the DB password at connection time rather
  than at task start, so a rotation requires no restart at all.
- **CAP-6**: Local development, docker-compose, and CI continue to work
  with a plain `DATABASE_URL` and no Secrets Manager access.

## Feature requirements

### FR-1: Unblock the deploy path on `main`

The 3 failing tests in `app/test/features/activity/imports_tab_test.dart`
pass, and the `deploy-images (parser)` and `deploy-web` failures from
the 2026-05-03 runs are resolved or confirmed no longer reproducing. A
push to `main` runs `deploy-services` to completion.

### FR-2: Credential-aware health probe

`GET /v1/health` verifies that a **new** database connection can be
established, not merely that a pooled one still works. It returns 503
only when the failure is an authentication failure (PostgreSQL SQLSTATE
`28P01` or `28000`); any other database error — timeout, connection
refused, DNS — leaves the endpoint returning 200, because replacing the
task cannot fix those and mass replacement converts a transient blip
into a full outage. The fresh-connection check is rate-limited so
health-check traffic does not open a TLS handshake per probe.

### FR-3: Worker liveness

The worker task definition gains a health check. It currently declares
none (`healthStatus: UNKNOWN`), so ECS has no mechanism to detect or
replace a broken worker under any failure mode.

### FR-4: Rotation-triggered redeployment

An EventBridge rule matches the native Secrets Manager `Secret Label
Updated` event for the `AWSCURRENT` label on the RDS-managed secret, and
triggers a forced new deployment of the api and worker ECS services.
The rule is defined in Terraform alongside the other infrastructure.

### FR-5: Connect-time credential resolution

When a `DB_PASSWORD_SECRET_ARN` is configured, engines resolve the
database password from Secrets Manager at connection time, with a TTL
cache and a cache-invalidate-and-retry-once on authentication failure.
When it is absent, behavior is exactly today's (`DB_PASSWORD` env var),
so local and CI paths are untouched. The ECS **task** roles gain
`secretsmanager:GetSecretValue` on that secret — today the permission
sits on the execution role, which the application cannot use.

### FR-6: Deploy-freeze visibility

A check surfaces when the deployed prod image falls more than 7 days
behind `main`, so a silent deploy freeze cannot persist for three
months again.

## Evals seed

- Rotate the secret; API 5xx window stays under 5 minutes without human
  action.
- Health endpoint returns 503 on a simulated `28P01`, 200 on a
  simulated connection timeout.
- Fresh-connection probe opens at most one new connection per rate-limit
  window regardless of probe frequency.
- Secret Label Updated event → both ECS services show a new deployment.
- With `DB_PASSWORD_SECRET_ARN` unset, engine construction is
  byte-identical to today's behavior.
- Password rotated mid-process: the next connection succeeds without a
  restart, after exactly one cache invalidation and retry.
- Deployed image age check fires when prod is more than 7 days behind.

## Open questions

- Whether the 2026-05-03 `deploy-images (parser)` failure still
  reproduces on current `main`, or was fixed incidentally — owner:
  research (Phase 1 resolves by running CI).
- Whether FR-6 belongs as a CI job, a scheduled cloud check, or a
  CloudWatch alarm — owner: user, at Design.

## Reference links

- Spec: `plan/plan-462355-2026-07-27T10:51-rotation-self-heal.md`
- Incident evidence: CloudWatch `/ecs/palateful-api-prod`, first
  `OperationalError` 2026-07-21; CloudTrail `RotationSucceeded`
  2026-07-21T21:29:14.
- Prior art: `e74303f` (undeployed health probe), memory
  `project_db_credential_cleanup.md` (2026-04-15 refactor + gotchas).
- `docs/PERFORMANCE_OPS.md`, `CLAUDE.md` § Ops Scripts.
