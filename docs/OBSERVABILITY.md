# Observability — Endpoint & Task Latency

Operator guide for the latency-metrics surface shipped in the
**epic-observability-latency** epic (2026-04-18).

## How capture works

Every matched FastAPI route and every Celery task lifecycle writes one
row via a **`BatchedLatencyWriter`** (see
`libraries/utils/utils/services/observability/batched_latency_writer.py`).

- **API side** — `LatencyCaptureMiddleware`
  (`services/api/src/middleware/latency_capture.py`) measures
  `time.perf_counter()` around `call_next`. Skips `/health`, `/ready`,
  and any request whose `scope["route"]` is unset (404s, static paths).
- **Worker side** — Celery signal handlers in
  `libraries/utils/utils/services/observability/celery_hooks.py` hook
  `task_prerun` / `task_postrun` / `task_failure` / `worker_shutdown`.
- The writer buffers up to 10 000 samples in a `queue.Queue` and flushes
  in bulk **on first of: 100 samples, 2 s, or shutdown**. Drop-oldest
  on queue-full; dropped count is WARN-logged at most once / minute.

## Tables

Both are append-only heap tables (no partitioning at expected volume):

- `request_latencies` — `method, normalized_path, status_code,
  duration_ms, user_id, request_id, created_at`
- `task_latencies` — `task_name, task_id, duration_ms, status
  (success|failure|retry), queue_name, created_at`

Each has a composite index `(created_at DESC, <grouping key>)` + a
`(created_at DESC)` index for the overall-p95 top-stat query.

## Admin UI

Visit `Profile → Admin Dashboard`:

- Top stats include **p95 (24h)** and **Slowest (24h): method path —
  p95 ms**. Null on cold start / empty dataset.
- Tap **Metrics** to reach `/admin/metrics` — the endpoint + task
  tables with a 1 h / 24 h / 7 d window selector, p50/p95/p99 columns,
  error- and failure-rate columns, and a 24-bucket mean-latency
  sparkline per row.

## Ad-hoc queries

Useful SQL while debugging:

```sql
-- p95 per endpoint, last 24 h
SELECT
  method,
  normalized_path,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms,
  COUNT(*) AS n
FROM request_latencies
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY method, normalized_path
ORDER BY p95_ms DESC
LIMIT 20;

-- Task failure rate, last 7 days
SELECT
  task_name,
  COUNT(*) FILTER (WHERE status = 'failure')::float / COUNT(*) AS fail_rate,
  COUNT(*) AS n
FROM task_latencies
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY task_name
ORDER BY fail_rate DESC;
```

## Retention

Nightly Celery beat task **`cleanup_latency_samples`** runs at
**02:00 UTC** and deletes rows older than **30 days** from both
tables. Registration lives in `libraries/utils/utils/services/celery.py`
alongside `cleanup-error-logs`. Re-runs are no-ops.

## Verifying no sample loss

```bash
# In the API container's stdout, look for the hourly WARN:
grep "BatchedLatencyWriter" container.log | grep "dropped"
```

A zero match means the queue has kept up. A line like
`dropped 8 samples in the last ~60s` is usually fine — capture is
best-effort, and 8 / ~18000/hr is a rounding error. If you see sustained
drops on every interval (≥100 / min), the DB flush is lagging; check
for pool exhaustion or an outage.

## Escalation — table size

```sql
SELECT pg_size_pretty(pg_total_relation_size('request_latencies')) AS req,
       pg_size_pretty(pg_total_relation_size('task_latencies'))    AS task;
```

If the combined total ever crosses **~2 GB** on RDS:

1. First, **tighten retention to 14 d** — edit `RETENTION_DAYS` in
   `libraries/utils/utils/tasks/observability_tasks/cleanup_latency_samples.py`
   and redeploy. The next nightly run will do the heavy prune.
2. Only after retention tightening should partitioning / downsampling
   be considered. Those options are intentionally out of scope at
   friends-and-family volume.

## Chaos verification (manual, periodic)

```bash
# 1. Take the DB briefly unreachable (local dev with docker-compose):
docker compose stop db

# 2. Hit the API a few times:
curl -sS http://localhost:8000/v1/health    # skipped by capture — OK
curl -sS http://localhost:8000/v1/user/me   # authed — captured + queued

# 3. Watch the API log for a WARN from
#    `utils.services.observability.batched_latency_writer`:
#    "BatchedLatencyWriter[request_latencies] failed to flush N samples…"
#    The request itself still returned 200 — capture must never surface
#    an error to the client.

# 4. Bring the DB back:
docker compose start db

# 5. Within ~2 s the next flush succeeds; new hits land normally in
#    request_latencies.
```
