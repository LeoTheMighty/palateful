<!-- refined via party-mode 2026-04-21 -->

# Epic: Performance — Infra Floor + Measurement Foundation

## Overview

The absolute latency floor of Palateful prod is set by infra: a `db.t4g.micro` that exhausts burst credits under any sustained query, an untuned PostgreSQL parameter group, an ECS API task at 256 CPU / 512 MB where Auth0 JWT verification competes with DB work for CPU, and a JWKS cache that cold-starts on every task restart. On top of that, `epic-observability-latency` is deployed and collecting data, but there's no CLI that turns that data into "show me the top-N slowest endpoints right now" or "what regressed in the last 24h versus the prior 30d baseline?"

This epic lifts the floor and lights up the measurement surface. It is the foundational epic of the Performance Health Initiative — every downstream story (in `epic-perf-backend-query-tuning` and `epic-perf-flutter-client-polish`) captures before/after numbers via the ops script shipped here, so fixes are proved, not assumed.

## Goal

- Ship `analyze_latency.py` **first** (pim-1) so a pre-upgrade baseline is captured before any other change lands.
- Reduce absolute p95 on the five hot-path endpoints (`GET /v1/meals?scope=home`, `GET /v1/recipes`, `GET /v1/shopping-lists`, `GET /v1/activities`, `GET /v1/calendars`) by a measured amount once `pim-3` lands. The brag metric is the **delta from pre-upgrade baseline** captured in pim-1, not an absolute number.
- Eliminate JWKS cold-fetch as a latency contributor on task restarts (Redis warm-across-deploys, single-flight on concurrent cold-starts).
- Unlock the two downstream epics by giving them a cheap, before/after-comparable measurement primitive.

Total incremental infra cost: +~$15/mo (under NFR29's $50 cap).

## End-User Flow

End user here is Leo (the only current user), wearing the operator hat.

1. **Baseline capture** (pre-epic): Before any infra change lands, Leo runs `DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py --window 24h --top 15 --format csv > /tmp/baseline.csv`. This snapshot is pinned in the story's QA walkthrough.
2. Later, after `pim-2` (parameter group) and `pim-3` (instance upgrade) land, Leo reruns the same command → `/tmp/post.csv`. He diffs the two; the brag is "p95 of `GET /v1/meals?scope=home` dropped from Yms to Xms — a Z% drop."
3. Leo opens Profile → Admin → Metrics. The existing dashboard still works (no change).
4. For deeper investigation he runs `analyze_latency.py --regression-hunt`. Output shows endpoints whose recent-24h p95 is >1.5× their 7–30d baseline. Anything above that threshold feeds `epic-perf-backend-query-tuning`.
5. When Leo opens CloudWatch Logs → `/aws/rds/instance/palateful-prod-db/postgresql`, every query >100ms is logged with EXPLAIN context.
6. After a deploy, Auth0 JWKS stays warm in Redis; first-request-per-task no longer pays a ~200ms cold-fetch penalty. Even if five tasks cold-start concurrently, only one fetches from Auth0 (single-flight) and the rest get the same value from Redis.
7. **During the RDS maintenance window** (pim-3), Leo stops using the app; Flutter surfaces a recoverable error state; no silent data loss on in-flight writes. Confirmed in QA.
8. After everything lands, downstream epics (`epic-perf-backend-query-tuning`, `epic-perf-flutter-client-polish`) can each cite the ops script for per-endpoint wins.

## Frontend Changes

**Indirect only — no Flutter code changes.**

One verification required: during the RDS maintenance window in `pim-3`, confirm the Flutter app shows a recoverable error state (existing error-card pattern in `api_client`) and does not crash-loop on the 5–10-minute DB outage. No code change expected; this is a smoke test, not a feature.

## Backend Changes

- **New ops script** `services/api/scripts/analyze_latency.py`. Read-only — no mutations, no audit row. Argparse mirrors `fetch_feedback.py` (same `--format`/streaming patterns). Flags:
  - `--window {1h|24h|7d|all}` (default `24h`) — time-range filter
  - `--format {table|csv|json}` (default `table`)
  - `--top <int>` (default `15`, max `100`) — per-section row cap
  - `--regression-hunt` — swaps the main query for the recent-vs-baseline CTE in the architecture addendum
  - `--min-samples <int>` (default `5`) — server-side `HAVING COUNT(*) >= N` noise floor; `--min-samples 0` disables
  - `--section {endpoints|tasks|both}` (default `both`)
  - Default sort: **p95 desc** (documented on `--help`)
  - Exit codes: `0` rows emitted, `2` empty (informational), `1` DB / runtime error
- **Two SQL query shapes** (bodies in architecture addendum 2026-04-21).
- **Connection pool config** in `libraries/utils/utils/constants.py` — `DB_POOL_SIZE` default 10 → **20**, `DB_MAX_OVERFLOW` default 20 → **40**. Both env-overridable. Pair with `max_connections=80` in the RDS parameter group (leaves 20 for beat/worker/migrator/psql).
- **Auth0 JWKS cache relocation** — `libraries/utils/utils/services/auth0.py` today keeps `_jwks: dict` as a module global. Replace with a `JwksCache` class that reads/writes Redis via `redis.asyncio`, falls back to module-global in-memory on Redis failure (connect/op timeout). 1h TTL. Background refresher runs 10 min before expiry. **Single-flight lock** on concurrent cold-fetches (e.g., `asyncio.Lock` keyed to `(issuer, kid)`) so five parallel task cold-starts trigger one Auth0 round-trip, not five. **Stale-but-present hit**: if Redis returns a value past soft-TTL but before hard-TTL, serve it and trigger an async refresh; test path enumerated.
- **New `libraries/utils/utils/services/redis_client.py`** — thin async `redis.asyncio` wrapper with a connection pool (max_connections=10, 100ms connect / 50ms op timeout). Exposes `get_redis()` returning a shared client or `None` if `REDIS_URL` is unset / unreachable. Clients never raise to the caller; failure is `None`.
- **ENV additions** (all optional in non-prod): `REDIS_URL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`.
- **Migration backport** — survey `services/migrator/migrations/versions/` for `CREATE INDEX` (non-CONCURRENTLY) statements on tables that carry prod data. Any finding → paired forward migration using `CREATE INDEX CONCURRENTLY IF NOT EXISTS`. Historical migrations left alone. If the audit finds **nothing**, story closes with a commit message summarizing the audit (no empty migration file).
- **No API shape changes.** No endpoint gains or loses a field; no new routes.

## Infrastructure Changes

- **RDS maintenance window** — set `maintenance_window = "tue:07:00-tue:08:00"` (midnight Pacific, low-risk for single-user prod) on the RDS module **before** pim-2 or pim-3 so AWS doesn't pick its own slot mid-change. **Subject to user confirmation** (see Open Questions).
- **RDS instance class**: `terraform/modules/rds/main.tf` — `instance_class = "db.t4g.small"` (from `db.t4g.micro`). Applied during the maintenance window; `apply_immediately=false`. `deletion_protection=true` retained. ≈ +$10/mo. Rollback: `instance_class="db.t4g.micro"`, `apply_immediately=true`, ~5 min reboot.
- **RDS parameter group**: new `aws_db_parameter_group` keyed to `postgres16`:
  - Dynamic (no reboot): `work_mem=8MB`, `maintenance_work_mem=128MB`, `effective_cache_size=1500MB`, `log_min_duration_statement=100`.
  - **Static (reboot required on `pending-reboot`)**: `shared_buffers=256MB`, `max_connections=80`.
  - Each AC calls out which are static vs dynamic. Post-apply verify via `SHOW shared_buffers;` / `SHOW max_connections;`.
- **Performance Insights**: `performance_insights_enabled=true`, `performance_insights_retention_period=7`. Free for 6 months on t4g.small; then ~$2/mo still within cap. **Operational hook**: calendar reminder in `BUGS.md` at day 170 to decide stay/drop.
- **`enabled_cloudwatch_logs_exports=["postgresql"]`** — slow-query log to existing log group.
- **ECS API task**: `terraform/modules/ecs/main.tf` — API task_definition `cpu=512`, `memory=1024` (from 256 / 512). Worker unchanged. ≈ +$5/mo.
- **ALB health check**: `terraform/modules/alb/main.tf` — `interval=60`, `timeout=3` (from 30 / 5). Confirms hung-task detection within 2 min; ECS circuit-breaker still protects deploys (no AC change required — existing protection covers the 1-min-longer window).
- **ElastiCache Redis**: new `aws_elasticache_replication_group`, one `cache.t4g.micro` node, same VPC private subnets, no multi-AZ, no replicas. SG allows **API task SG + Worker task SG** in on 6379 (worker doesn't currently call authenticated endpoints, but beat may schedule tasks that do — defensive). ≈ +$1/mo.
- **SSM Parameter `REDIS_URL`** — SecureString written by terraform from the ElastiCache endpoint.
- **Total infra cost delta**: ≈ +$15/mo (within NFR29).
- **No Lambda, API Gateway, or S3 changes.**

## Design Principles (refined via party-mode 2026-04-21)

- **Measure first, tune second.** `pim-1` is a **hard gate** for capturing before-numbers on pim-2, pim-3, pim-4a, pim-4b, pim-5. Every story's AC requires pre-upgrade numbers, not just post.
- **No breaking contracts.** Zero API shape changes. Every backend primitive that changes (pool, JWKS cache) keeps its public interface byte-compatible.
- **Cost visible in terraform.** Each terraform PR carries a one-line cost-delta comment so NFR29 is enforceable by review.
- **Fail open on Redis; single-flight on cold start.** Auth0 JWT verify must work if Redis is gone. Concurrent cold-fetches must not stampede Auth0.
- **Parameter changes are reversible.** Parameter group is its own resource; rollback is a one-terraform flip. Instance class is reversible via `apply_immediately=true` + 5 min reboot (no snapshot restore needed).
- **`CONCURRENTLY` for every forward index.** No new migration blocks production traffic on DDL.
- **Telemetry noise floor is explicit.** `--min-samples 5` by default; opt out with `--min-samples 0`. No silent trimming.
- **Static params are gated on reboot.** Pool bump (pim-4b) gated on pim-2 reboot completion; `SHOW max_connections` verified in prod pre-merge.
- **Terraform lives here only.** The two downstream perf epics never touch `terraform/`. If they need infra, they punt back here.

## File Structure

Anticipated touched / new paths:

**Backend:**

```
services/api/scripts/analyze_latency.py                                  (new)
libraries/utils/utils/services/redis_client.py                           (new)
libraries/utils/utils/services/auth0.py                                  (modify — JWKS cache via Redis, single-flight lock)
libraries/utils/utils/services/__init__.py                               (modify — export redis_client)
libraries/utils/utils/constants.py                                       (modify — pool defaults)
services/api/src/db/__init__.py                                          (modify — read env overrides)
libraries/utils/tests/test_redis_client.py                               (new — incl. connect-refused + timeout paths)
libraries/utils/tests/test_auth0_jwks_cache.py                           (modify — Redis path + stale-hit + single-flight)
services/api/tests/test_analyze_latency_script.py                        (new — incl. 1M-row microbenchmark)
```

**Infra:**

```
terraform/modules/rds/main.tf                                            (modify — instance class, param group, PI, maintenance_window)
terraform/modules/rds/parameter_group.tf                                 (new — aws_db_parameter_group)
terraform/modules/ecs/main.tf                                            (modify — API cpu/memory)
terraform/modules/alb/main.tf                                            (modify — health-check interval/timeout)
terraform/modules/elasticache/main.tf                                    (new — t4g.micro Redis)
terraform/modules/elasticache/variables.tf                               (new)
terraform/modules/elasticache/outputs.tf                                 (new)
terraform/environments/prod/main.tf                                      (modify — wire module + SSM)
terraform/environments/prod/outputs.tf                                   (modify — expose Redis endpoint)
```

**Migrations** (conditional on audit):

```
services/migrator/migrations/versions/<ts>_concurrently_<name>.py         (conditional — only if audit finds targets)
```

**Docs:**

```
docs/PERFORMANCE_OPS.md                                                   (new — analyze_latency usage + runbook)
BUGS.md                                                                   (modify — calendar note at day 170 re: PI free tier)
```

## Stories

**`pim-1-analyze-latency-script`** — Ship the read-only ops script. Cost-neutral. **Hard gate for pim-2..pim-5.**

ACs:
- `analyze_latency.py` with no flags prints a table of top-15 endpoints by p95 (24h) + top-15 tasks, returns `0` if rows, `2` if empty.
- `--format csv` emits RFC-4180 CSV; `--format json` emits NDJSON.
- `--window all` omits the `created_at` filter; other windows translate to `NOW() - INTERVAL '...'`.
- `--regression-hunt` runs the CTE query from the architecture addendum.
- `--min-samples 0` disables the noise floor; default `5`.
- `--section {endpoints|tasks|both}` limits output.
- **Default sort: p95 desc** — documented in `--help`.
- Exit codes 0/1/2 per spec.
- Script requires `DATABASE_URL`; exits `1` with explicit error if unset.
- **Microbenchmark**: runs in <5s against a 1M-row seeded `request_latencies` table.
- `docs/PERFORMANCE_OPS.md` documents every flag + a sample `--regression-hunt` invocation.
- **Baseline capture**: before pim-2 merges, Leo runs the script on prod and pastes the 24h top-15 CSV into pim-2's QA walkthrough file.

**`pim-2-rds-parameter-group-and-performance-insights`** — Cost-neutral RDS tuning.

ACs:
- Set `maintenance_window = "tue:07:00-tue:08:00"` on the RDS module (or confirmed alternate per Open Question).
- New `aws_db_parameter_group` named `palateful-prod-pg16-perf` with the values listed under "Infrastructure Changes."
- **Enumerate** which params are dynamic vs static in the story body and in the commit message: `shared_buffers` + `max_connections` = static (reboot required); `work_mem`, `maintenance_work_mem`, `effective_cache_size`, `log_min_duration_statement` = dynamic.
- `performance_insights_enabled=true`, retention 7.
- `enabled_cloudwatch_logs_exports=["postgresql"]`.
- `apply_immediately=false`; static params land on the next maintenance-window reboot.
- Terraform plan captured in QA walkthrough — no unexpected replacements.
- Post-apply verification: `SHOW shared_buffers` returns `256MB`; `SHOW max_connections` returns the target value; slow-query log visible in CloudWatch; PI dashboard active.

**`pim-3-rds-instance-upgrade`** — Biggest single lever.

ACs:
- `instance_class="db.t4g.small"`.
- **Pre-flight**: manual RDS snapshot captured before merge (answer to Open Question). Snapshot id recorded in QA walkthrough.
- Change scheduled during the `tue:07:00-tue:08:00` maintenance window.
- `deletion_protection=true` retained.
- **Baseline + post p95** captured via pim-1 for the five hot-path endpoints.
- **Flutter smoke**: during the reboot, manually confirm Flutter app shows a recoverable error card (existing `api_client` behavior), no crash loop, no silent write loss.
- **Rollback runbook** in QA walkthrough: `instance_class="db.t4g.micro"`, `apply_immediately=true`, ~5 min reboot. Drop a CloudWatch alarm on `CPUCreditBalance` depleting below 100 so any future regression surfaces.
- Post-apply `CPUCreditBalance` graph (CloudWatch) shows non-depleting behavior over 24h.

**`pim-4a-ecs-api-task-sizing`** — API task CPU/mem bump (isolated from pool/ALB changes for clean rollback).

ACs:
- API task_definition `cpu=512`, `memory=1024`.
- Rolling deploy; no task churn beyond normal.
- Post-apply: p99 CPU < 80% under normal load; no OOM-kill events in CloudWatch Logs.
- Rollback: revert task_definition; one terraform apply.

**`pim-4b-pool-and-alb-health-check`** — Config-only changes; gated on pim-2 reboot completion.

ACs:
- **Gate**: verify `SHOW max_connections` in prod matches target value before merge.
- `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` set to the pair chosen per Open Question, env-overridable.
- ALB target group health check `interval=60`, `timeout=3`.
- Post-apply: no health-check flap; no `too many connections` errors in logs; ECS circuit-breaker still engages on deploy failure.
- Unit test covers env-override read path.

**`pim-5-redis-and-jwks-cache`** — Introduce Redis; move Auth0 JWKS cache to it.

ACs:
- Terraform creates `cache.t4g.micro` ElastiCache + writes `REDIS_URL` to SSM; SG allows API + Worker SGs in on 6379.
- `redis_client.py` exposes `get_redis()` → client or `None`; unit tests cover connect-refused, op-timeout, `None` return.
- `Auth0.get_jwks()` reads from Redis first; falls back to in-memory `_jwks: dict` on Redis miss/timeout; never raises.
- 1h hard TTL; 50-min soft TTL. **Stale-but-present hit**: serves cached value, triggers async refresh; frozen-time unit test verifies.
- **Single-flight lock**: concurrent cold-fetches trigger one Auth0 round-trip. Integration test: five parallel `get_jwks()` calls → one Auth0 fetch observed (mocked).
- **Prod canary**: after initial deploy, run a short-lived task-def revision with `REDIS_URL=redis://nonexistent:6379` for 10 min; assert zero 5xx, fail-open served every request. Revert revision.
- Post-deploy: JWT-verify p95 on task-restart measurably drops (captured via pim-1 for any `authenticate_user`-dependent endpoint).

**`pim-6-concurrently-migration-backport-audit`** — Audit + conditional fix.

ACs:
- Survey `services/migrator/migrations/versions/` for `op.execute("CREATE INDEX ...")` without `CONCURRENTLY`.
- For each finding: forward migration creates the equivalent index `CONCURRENTLY IF NOT EXISTS`; historical file unchanged.
- If **no findings**, story closes with a commit `chore(migrations): audit — no legacy non-CONCURRENTLY indexes` and a paragraph listing the migrations surveyed. No empty migration committed.
- Every new migration uses `with op.get_context().autocommit_block():` and includes a `downgrade()` dropping the index.

## Dependencies

- **Blocks**: `epic-perf-backend-query-tuning` (soft — QA walkthroughs cite pim-1 numbers), `epic-perf-flutter-client-polish` (soft — pfc-5 cites pim-1 numbers).
- **Blocked by**: nothing. All upstream primitives exist.
- **Internal**: pim-1 is a hard gate for pim-2/3/4a/4b/5 (pre-change baseline capture). pim-4b gates on pim-2 reboot completion (static param sequencing). pim-5 can proceed in parallel with pim-2/3/4.
- **Shares with**: nothing in the current sprint. Disjoint surfaces.

## Locked Decisions (propagate to sibling epics)

1. **Pool arithmetic** — final values decided at the user gate; whichever pair is chosen, **downstream epics must not bump it** without re-verifying against `max_connections`.
2. **Every perf story's QA walkthrough captures p50/p95 for the target `normalized_path` before + after**, via `analyze_latency.py --window 24h`, pasted into the story file. Before-numbers are a **hard AC**, not a nice-to-have.
3. **Redis is for Auth0 JWKS only in this initiative.** Downstream caching proposals open their own scope gate.
4. **Any new index** in this or downstream epics uses `CREATE INDEX CONCURRENTLY` inside `op.execute()` wrapped in an autocommit block.
5. **Terraform lives in `epic-perf-infra-and-measurement` only.** Neither sibling epic touches `terraform/`. If they need infra, they punt back here.
6. **Fail-open semantics are mandatory for every cache layer.** Redis unreachable → in-memory fallback → request succeeds.

## Risks + Mitigations

- **Static-param pool mismatch** (pool bump ships before reboot → `too many connections`): gate pim-4b merge on pim-2 reboot completion; `SHOW max_connections` pre-check.
- **RDS reboot outage during pim-3** (~5 min Flutter error state): schedule maintenance window; pre-announce; smoke-test graceful error UI.
- **`work_mem=8MB` plan regressions**: pim-1 `--regression-hunt` catches within 24h; rollback is a param-group flip.
- **JWKS stampede on cold-start**: single-flight lock in pim-5 AC; integration test.
- **ElastiCache single-point failure** (no multi-AZ): fail-open to in-memory is the design; document degraded-not-broken in `PERFORMANCE_OPS.md`. Revisit multi-AZ only if Redis scope expands.
- **PI free-tier expiry**: calendar reminder day 170; still under $50 cap either way.
- **pim-6 audit empty**: acceptable no-op close; commit message summarizes; no empty migration.

## Open Questions for the User — RESOLVED (2026-04-21)

1. **Maintenance window** — confirmed `tue:07:00-tue:08:00` UTC (midnight Pacific).
2. **Pool arithmetic** — Option A: `max_connections=80` in the parameter group; `DB_POOL_SIZE=20 / MAX_OVERFLOW=40`. Decision pinned.
3. **Pre-flight snapshot for pim-3** — **default yes**; 2-minute manual RDS snapshot before merge, snapshot id pasted into the pim-3 QA walkthrough. Revisit only if the user explicitly opts out.
