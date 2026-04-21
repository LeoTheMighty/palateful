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
| `--regression-hunt` | off | Swaps the main query for a recent-24h vs 7-to-30d-baseline CTE. Flags endpoints whose recent p95 is > 1.5× baseline p95 with >= 10 recent samples. Implies `--section endpoints`. |
| `--min-samples` | `5` | `HAVING COUNT(*) >= N` noise floor. `0` disables. |
| `--section` | `both` | `endpoints`, `tasks`, or `both`. |

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
