# Performance Ops

Operator runbook for the Palateful Performance Health Initiative.

All performance-related decisions (parameter-group tunes, instance-class
upgrades, pool bumps, client-polling merges) are grounded in before/after
numbers captured via `services/api/scripts/analyze_latency.py`. Every
perf story's QA walkthrough pastes the CSV output of this script for
the target endpoint's `normalized_path` — no fix lands without a
measured delta.

## `analyze_latency.py`

Read-only script. Queries `request_latencies` + `task_latencies` (the
Postgres-backed tables shipped by `epic-observability-latency`) and
surfaces the top-N slowest endpoints + tasks by p95. Writes nothing,
no audit row.

### Flags

| Flag | Default | Description |
|---|---|---|
| `--window` | `24h` | `1h`, `24h`, `7d`, or `all`. Controls the `created_at >=` filter. |
| `--top` | `15` | Rows per section. Clamped to `[1, 100]`. |
| `--format` | `table` | `table` (human-readable), `csv` (RFC-4180), `json` (NDJSON, one object per line). |
| `--regression-hunt` | off | Swaps the main query for a recent-24h vs 7-to-30d-baseline CTE. Flags endpoints whose recent p95 is > 1.5× baseline p95 with >= 10 recent samples. Default scope: endpoints (`--section endpoints`). Combine with `--section client` / `all` to extend. |
| `--min-samples` | `5` | `HAVING COUNT(*) >= N` noise floor for endpoints/tasks. `0` disables. |
| `--client-min-samples` | `50` | Noise floor for the client section. Client perf is noisier (network variance, device heterogeneity) so the default is higher than server. `0` disables. |
| `--section` | `both` | `endpoints`, `tasks`, `client`, `both` (endpoints + tasks — backward-compatible default), or `all` (endpoints + tasks + client). |

**Default sort**: p95 desc across every shape.

### Exit codes

- `0` — rows emitted.
- `1` — DB / runtime error, or `DATABASE_URL` unset.
- `2` — zero rows matched (informational — not a failure).

### Recipes

#### Capture the pre-change baseline

Run this before any infra change (pim-2/pim-3/pim-4a/pim-4b/pim-5)
lands. Paste the resulting CSV into the target story's QA walkthrough.

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --top 15 --format csv > /tmp/baseline-$(date +%Y%m%d).csv
```

#### Capture the post-change delta

After the change has been live for >= 1h (enough to settle), rerun the
same command as `post.csv` and diff:

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --top 15 --format csv > /tmp/post-$(date +%Y%m%d).csv

diff /tmp/baseline-*.csv /tmp/post-*.csv | less
```

The brag metric is the delta from the pinned pre-change baseline for
the five hot-path endpoints:

- `GET /v1/meals?scope=home`
- `GET /v1/recipes`
- `GET /v1/shopping-lists`
- `GET /v1/activities`
- `GET /v1/calendars`

#### Is it backend or frontend? (`--section all`)

Once `epic-perf-client-analytics` has 24h of data in `client_latencies`,
one invocation prints server + client tables together. Use this when
the app "feels slow" and you don't know which side is to blame:

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --section all --window 24h --top 20
```

Example output (abbreviated):

```
endpoints (top by p95 desc)
  METHOD  PATH                             COUNT   P50   P95   P99   MAX
  GET     /v1/recipes/{recipe_id}            450   120   340   920  1800

tasks (top by p95 desc)
  TASK                     STATUS   COUNT   P50    P95    P99    MAX
  worker.import.ocr_extract  success  100  40000  55000  85000 120000

client (top by p95 desc)
  TYPE          PLAT   ROUTE                  COUNT   P50   P95   P99   MAX
  route_paint    ios   /recipes/:id            180   200  1100  2400  4500
  first_paint    web   /home                    95   380   820  1200  1600
```

Compare the client row's p95 against the matching server path — if
the server-side p95 is stable but the client paint jumped, the
regression is in Flutter (or network); if both jumped, it's backend.

#### Client-side regression hunt

Once client samples are flowing, extend the regression hunt to the
client table. Client threshold is **2.0×** (not server's 1.5×) because
client metrics are noisier; sample floor defaults to 50 instead of 10.

```bash
# Client only.
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --regression-hunt --section client --format table

# Server + client in one emission.
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --regression-hunt --section all --format json \
    > /tmp/regressions-$(date +%Y%m%d).jsonl
```

The client regression block groups by `(type, platform, route)`, so
an iOS-only `route_paint` regression on `/home` is a distinct row from
the Android version — useful when a platform-specific bug hits only
one client.

#### Hunt for regressions

Run this daily (or after every deploy) to catch endpoints that drifted
in the last 24h vs their 7-to-30d baseline. Anything with `pct_increase
> 50` feeds directly into `epic-perf-backend-query-tuning`.

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --regression-hunt --format table
```

Sample output:

```
regression_hunt (recent 24h p95 > 1.5x baseline p95, sorted by % increase)
  METHOD  PATH                                                 BASE_P95    CUR_P95        %    COUNT
  GET     /v1/meals                                               150.0      500.0    233.3       57
  GET     /v1/shopping-lists                                       80.0      200.0    150.0       42
```

#### Drill into a specific endpoint (no noise floor)

When you suspect a low-traffic endpoint, bypass the `HAVING COUNT(*)
>= 5` floor so every group is emitted. Use with `--top` generously.

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --section endpoints --window 1h --min-samples 0 --top 100
```

#### Task-side hot spots

Celery tasks live in a sibling `task_latencies` table and follow the
same PERCENTILE_CONT aggregation. Use `--section tasks` to surface
slow worker tasks independently.

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --section tasks --window 7d --format table
```

### Design choices

- **Streaming not buffered.** The aggregation collapses to `<= --top`
  rows inside Postgres, so the Python path isn't memory-bound.
- **No audit row.** Read-only: nothing to record.
- **Interval literals are hardcoded in SQL, not bound params.**
  `NOW() - INTERVAL '...'` doesn't accept a bind parameter in the
  `INTERVAL` literal; we interpolate from a closed enum of
  `{1h, 24h, 7d, all}` so there's no injection surface.
- **`--window all` allows no `created_at` filter.** On prod this means
  a full-table aggregate scan — expect seconds, not milliseconds. Use
  sparingly.

## Redis + Auth0 JWKS cache

Shipped in pim-5. ElastiCache (`cache.t4g.micro`, single node, no
multi-AZ) holds the Auth0 JWKS so it's warm across task restarts and
across concurrent task cold-starts.

**Fail-open semantics are non-negotiable.** If Redis is unreachable
(timeout, connect-refused, hostname invalid), the Auth0 verifier falls
back to its original in-memory `_jwks: dict` cache and the request
succeeds. Zero 5xx from Redis downtime — a Redis outage manifests as
"first request per task pays the cold-fetch penalty again," not
"requests fail."

If Redis itself is genuinely degraded (not just unreachable) and you
suspect stale JWKS, you can force a fresh fetch by bouncing the API
task — the new task starts with no Redis cache entry, the fail-open
path triggers, and fresh JWKS get repopulated into both tiers.

**ElastiCache single-node caveat**: one-zone deployment means an AZ
failure takes Redis with it. That's acceptable *only* because the
JWKS cache is fail-open. Any future use of Redis for application data
(session state, generic caching, etc.) would require revisiting the
multi-AZ decision.

## Parameter group — palateful-prod-pg16-perf

Introduced in pim-2. Static params (require reboot):

- `shared_buffers = 256MB`
- `max_connections = 80`

Dynamic params (hot-apply):

- `work_mem = 8MB`
- `maintenance_work_mem = 128MB`
- `effective_cache_size = 1500MB`
- `log_min_duration_statement = 100` (every query >100ms hits the
  slow-query log)

**Slow-query log consumption**: CloudWatch Logs Insights against the
`/aws/rds/instance/palateful-prod-db/postgresql` log group.

### Post-apply verification

```sql
SHOW shared_buffers;        -- expect 256MB
SHOW max_connections;       -- expect 80
SHOW work_mem;              -- expect 8MB
SHOW log_min_duration_statement;  -- expect 100
```

### Rollback

Parameter group is its own resource. Revert the terraform module to
remove the custom parameter group and the RDS instance falls back to
the default `postgres16` parameter group. Static params require one
reboot to unwind.

## RDS instance — db.t4g.small

Upgraded from `db.t4g.micro` in pim-3. Applies during the tue 07:00-08:00
UTC maintenance window.

### Rollback

```hcl
instance_class = "db.t4g.micro"
apply_immediately = true
```

~5 minute reboot. `deletion_protection=true` stays on throughout.

**CPUCreditBalance alarm**: post-upgrade, a CloudWatch alarm fires if
`CPUCreditBalance < 100` to catch any regression back to burst-credit
exhaustion.

## Connection pool

Shipped in pim-4b.

- `DB_POOL_SIZE = 20` (was 10) — env-overridable
- `DB_MAX_OVERFLOW = 40` (was 20) — env-overridable

Fits under `max_connections = 80` with 20 reserved for
beat/worker/migrator/`psql` sessions.

**Gate**: pim-4b cannot merge until pim-2's static-param reboot has
completed and `SHOW max_connections;` returns `80` in prod.

## ALB health check

Shipped in pim-4b.

- `interval = 60s` (was 30s)
- `timeout = 3s` (was 5s)

Trims health-check volume on the hot path. Hung-task detection still
fires within 2 min; ECS deployment circuit breaker still gates failed
deploys.

## Client-latency ingest kill-switch (`cla-1c`)

Shipped in cla-1c as the escape hatch for the client-side analytics
pipeline (`epic-perf-client-analytics`).

The pipeline ships ~125k rows/day into `client_latencies` at normal
scale. If the Postgres instance starts pushing against IOPS / storage
/ connection budget *during an incident*, we need to stop the writes
instantly — without shipping a new Flutter build (TestFlight / Play
review lag measured in days).

### Contract

- `GET /v1/flags/perf` returns `{ingest_enabled: bool, sampling_rate: float}`.
- Unauthenticated. Anonymous pre-login clients honor the switch too.
- Flutter fetches once per cold-start (after Firebase init), caches
  the result for 5 min, and **treats any error / timeout / unreachable
  response as defaults-on**. The endpoint therefore never returns a
  4xx / 5xx on the happy path.

### Environment variables (ECS task definition)

| Env var | Default | Effect |
|---|---|---|
| `CLIENT_LATENCY_INGEST_ENABLED` | `true` | When `false`, Flutter drops every enqueue on the floor — no retry, no disk buffer. Backend ingest endpoint keeps accepting (in case late-cached clients still POST), but write volume collapses within 5 min as clients refresh their flag cache. |
| `CLIENT_LATENCY_SAMPLING_RATE` | `1.0` | Fraction in `[0.0, 1.0]`. Client samples events at this rate BEFORE batching. Soft lever — use this when volume is annoying but not an incident (e.g. drop to `0.1` during a traffic burst). |

### Runbook: flip the kill-switch

1. Confirm the pain source. `bin/prod-script audit_errors.py --service api --window 1h` + `bin/prod-logs` + CloudWatch RDS CPU / IOPS.
2. ECS → `palateful-api-prod` service → Task definitions → create new revision.
3. Container env: set `CLIENT_LATENCY_INGEST_ENABLED=false` (or `CLIENT_LATENCY_SAMPLING_RATE=0.1` for the softer lever).
4. Update service to the new revision. Rolling deploy — zero downtime.
5. Within 5 min every client refreshes its flag cache and stops enqueuing.
6. Row-rate drop visible via `psql -c "SELECT count(*) FROM client_latencies WHERE created_at > now() - interval '5 minutes';"` — should trend to ~0.

### Re-enable

Reverse step 3 (`CLIENT_LATENCY_INGEST_ENABLED=true`, sampling back to `1.0`) and redeploy. Expect up to 5 min before field clients refresh.

### Reference

- Endpoint: `services/api/src/api/v1/flags/get_perf_flags.py`
- Router: `services/api/src/routers/v1/flags_router.py`
- Config: `services/api/src/config.py` (`client_latency_ingest_enabled`, `client_latency_sampling_rate`)
- Tests: `services/api/tests/test_perf_flags.py`

---

## Web renderer caveat (cla-9)

`WebPerfBridge` (`app/lib/core/services/web_perf_bridge.dart`) reads
browser `PerformanceNavigationTiming` + Paint Timing entries on web
only. When interpreting the dashboard, note:

- **Canvas renderer** (CanvasKit / Skia-over-WebGL): the app draws on a
  single `<canvas>` so the browser sees one paint event covering the
  whole shell. `first-paint` and `first-contentful-paint` therefore
  fire together at ~frame 1, regardless of content being ready.
- **HTML renderer**: each Flutter widget maps to DOM nodes. The browser
  sees successive paint events as real content mounts, so
  `first-contentful-paint` tracks closer to what users perceive as
  "content showed up."

When cross-comparing web vs. mobile in the admin Client tab, filter to
one renderer (via `platform=web` + `app_version`) at a time. A
regression that only moves the FP line on canvas builds is an engine /
bundle-size issue; one that moves FCP on the HTML renderer is usually
a widget-tree problem.
