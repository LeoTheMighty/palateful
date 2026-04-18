# Story obs-latency-2: Admin aggregation endpoints + /admin/stats extension

**Status:** in-progress
**Epic:** epic-observability-latency

## Goal
Expose the captured latency samples via three pieces of admin surface:
two new percentile-aggregation endpoints (endpoints + tasks) and a small
extension to the existing `/admin/stats` response so the dashboard header
can show "Overall p95 (24h)" and "Slowest endpoint (24h)".

## Scope
- `GET /v1/admin/metrics/endpoints?window={1h|24h|7d}` returns one row per
  `(method, normalized_path)` with p50/p95/p99/count/error_rate + a
  24-bucket sparkline of mean latency. Sorted by p95 desc.
- `GET /v1/admin/metrics/tasks?window={1h|24h|7d}` mirrors the shape for
  Celery tasks, keyed by `task_name`, with `failure_rate` (= rows with
  `status='failure'` / total).
- Both gate via `require_admin` and reject unknown `window` values with
  HTTP 400.
- `GET /v1/admin/stats` gains `overall_p95_ms` (24 h window) and
  `slowest_endpoint` (`{method, normalized_path, p95_ms}` over 24 h, or
  null on cold start).

## File List
- `services/api/src/api/v1/admin/get_endpoint_metrics.py` — new
- `services/api/src/api/v1/admin/get_task_metrics.py` — new
- `services/api/src/api/v1/admin/get_stats.py` — modified (union'd with
  feedback-2's shape; adds `overall_p95_ms` + `slowest_endpoint`)
- `services/api/src/api/v1/admin/__init__.py` — modified (export)
- `services/api/src/routers/v1/admin_router.py` — modified (2 routes)
- `services/api/tests/test_admin_metrics.py` — new

## Notes
- Each aggregation endpoint runs two queries: (1) percentiles + counts +
  error-rate per key; (2) 24-bucket mean over the window. Merging in
  Python is cheaper than stuffing both into a single CTE-with-
  generate_series monster — makes the SQL far easier to read and stays
  well under the NFR50 budget.
- The window is validated against a small allow-list (`1h`, `24h`, `7d`);
  a bad value returns `APIException(400)`. Matches the precedent set by
  `send_test_push.py` for param validation.
- `overall_p95_ms` reuses `percentile_cont` on the full `request_latencies`
  for the 24 h window. `slowest_endpoint` runs the same percentile groupby
  as the endpoint-metrics endpoint, but with `LIMIT 1` — ignoring the
  24-bucket sparkline query entirely.

## QA walkthrough
See `_bmad-output/implementation-artifacts/obs-latency-2-qa-walkthrough.md`.
