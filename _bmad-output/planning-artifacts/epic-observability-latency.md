<!-- refined via party-mode 2026-04-18 -->

# Epic: Operator Observability — Endpoint & Task Latency Metrics

## Overview

Add end-to-end latency visibility for the FastAPI backend and Celery worker to the existing admin dashboard (Epic 12). Today the admin dashboard has errors, logs, users, and stats — but nothing measuring how long any request or background task takes. Datadog and Prometheus are explicitly rejected (cost / ops). We are using Postgres as the metrics store via a new `BatchedLatencyWriter` primitive and exposing percentile tables in a new `AdminMetricsScreen`.

## Goal

When Leo suspects the app "feels slow," he opens the admin dashboard → Metrics, picks a time window (1h / 24h / 7d), and within two seconds sees exactly which endpoints and which Celery tasks have degraded — ranked by p95, with a sparkline showing the shape of the degradation over the window. The infrastructure this rides on costs nothing beyond existing RDS headroom (NFR29).

## End-User Flow

End user here is the admin (currently: Leo). Full narrative:

1. Leo is using the Palateful app on his phone. The home grid feels sluggish.
2. He opens Profile → Admin → Admin Dashboard. The dashboard header now shows an "Overall p95 (24h): 320ms" stat and a "Slowest endpoint (24h): GET /v1/recipes — 2.1s" strip at the top.
3. He taps the "Metrics" card on the dashboard.
4. `AdminMetricsScreen` loads at route `/admin/metrics`. At the top: a window selector (1h / 24h / 7d), defaulted to 24h. Below: two sections, each a sortable table.
5. **Endpoints section** — rows keyed by `(method, normalized_path)`: columns are `p50`, `p95`, `p99`, `count`, `error_rate`, and a small sparkline (24 equal-width buckets of mean latency over the window). Default sort: p95 descending.
6. Leo sees `GET /v1/recipes` at the top with a p95 of 2100ms and a sparkline that spikes over the last 3 hours. He now has a concrete target for investigation.
7. **Tasks section** below — same shape for Celery tasks keyed by `task_name`, plus a `failure_rate` column. Leo scrolls down and notices `worker.import.ocr_extract` has a p95 of 60s (expected — OCR is slow) and a failure_rate of 12% (suspicious).
8. Leo pulls down to refresh; both sections reload.
9. Leo switches the window to 1h to confirm the spike is recent. The tables re-query and the sparklines re-render.
10. Follow-up investigation happens outside this surface — he drops into the existing admin logs or errors screens, cross-referencing by timestamp. This epic does not add drill-down to per-request samples; that is intentionally deferred.

## Frontend Changes

- **New screen**: `app/lib/features/admin/admin_metrics_screen.dart`. Riverpod-provided state, `AsyncValue<AdminMetrics>` with a `WindowSelection` (1h / 24h / 7d) as provider parameter. Mirrors `admin_errors_screen.dart` in layout and pull-to-refresh behavior.
- **New widget**: `app/lib/features/admin/widgets/latency_sparkline.dart` — 24-bucket mini-chart drawn with `CustomPainter`, no external dependency. Takes a `List<double>` of 24 bucket means, renders as a polyline within a 60×20 dp box.
- **New widget**: `app/lib/features/admin/widgets/metrics_table.dart` — sortable table with columns (path/task, p50, p95, p99, count, error_rate/failure_rate, sparkline). Virtualized via `ListView.builder` for long lists.
- **Dashboard extension**: `admin_dashboard_screen.dart` — add two new stat tiles ("Overall p95 (24h)", "Slowest endpoint (24h)") and a new "Metrics" card that navigates to `/admin/metrics`.
- **Router**: add `/admin/metrics` to `app/lib/core/router/app_router.dart`. Gated by the existing `isAdminProvider` check (same as `/admin` / `/admin/errors`).
- **API client**: extend `app/lib/core/services/api_client.dart` with `getEndpointMetrics(window)` and `getTaskMetrics(window)` methods.
- **Freezed models**: `MetricRow`, `MetricWindow`, `EndpointMetrics`, `TaskMetrics` under `app/lib/features/admin/models/`.
- **Empty state**: when the window has zero samples (cold start, fresh deploy, mid-migration), render a one-line "No samples yet — check back after some traffic." No spinners past the initial shimmer.
- **Error state**: follows the existing admin-screen pattern (inline `ErrorCard` with retry).

## Backend Changes

- **Migration** (`services/migrator/migrations/versions/<ts>_add_latency_tables.py`): create `request_latencies` and `task_latencies` tables with indexes per the architecture addendum (2026-04-18). Schema is exhaustively defined there; migration mirrors it.
- **New SQLAlchemy models**: `libraries/utils/utils/models/request_latency.py` and `task_latency.py`. Follow existing model conventions (UUID id, `Base.created_at`).
- **New primitive**: `libraries/utils/utils/services/observability/batched_latency_writer.py`. Singleton per process, `asyncio.Queue` (API) + `queue.Queue` (Celery worker). Async background task flushes on 100 samples or 2s. SIGTERM handler drains the queue. Drop-oldest on queue-full; drop counter logged every minute. 100% unit-test-covered because it is the load-bearing piece.
- **FastAPI middleware**: `services/api/src/middleware/latency_capture.py`. Registered in `main.py` after `ErrorTrackingMiddleware`. Captures `start = time.perf_counter()`, on response computes `duration_ms = int((perf_counter() - start) * 1000)`, uses `request.scope["route"].path` (the template) for normalization, skips `/health` + `/ready`, enqueues into the writer.
- **Celery signal handlers**: `libraries/utils/utils/services/observability/celery_hooks.py`. `task_prerun` stashes `start_time` on task context; `task_postrun` and `task_failure` compute duration and enqueue. Imported from `libraries/utils/utils/services/celery.py` so handlers register at worker boot.
- **Aggregation endpoints** (`Endpoint` class pattern):
  - `services/api/src/api/v1/admin/get_endpoint_metrics.py` — `GET /v1/admin/metrics/endpoints?window={1h|24h|7d}`. Single query using `percentile_cont(0.5 | 0.95 | 0.99) WITHIN GROUP (ORDER BY duration_ms)` grouped by `(method, normalized_path)`, plus a correlated subquery or CTE with `generate_series` for the 24-bucket sparkline. Query plan captured in story AC.
  - `services/api/src/api/v1/admin/get_task_metrics.py` — mirrors for tasks.
- **Admin stats extension**: `services/api/src/api/v1/admin/get_stats.py` — add `overall_p95_ms` (24h) and `slowest_endpoint` (`{method, normalized_path, p95_ms}`) to the response. Null when no samples yet.
- **Nightly prune**: `libraries/utils/utils/tasks/observability_tasks/cleanup_latency_samples.py` — registered on the existing Celery beat schedule in `celery.py` at the same 02:00 UTC slot as `cleanup_error_logs`. `DELETE FROM request_latencies WHERE created_at < now() - interval '30 days'`; same for `task_latencies`. Idempotent.
- **Shutdown hook** in `services/api/src/main.py` — on FastAPI lifespan `shutdown`, drain the writer queue so samples from the last 2 seconds aren't lost on deploy.

## Infrastructure Changes

- **None.** Tables land via existing `services/migrator`; writer + endpoints ship in the existing ECS API task; prune task ships in the existing ECS worker. No new AWS resources, no Terraform changes, no secrets.
- **CloudWatch**: the drop-count log line uses the existing log group. No new log groups, alarms, or metric filters.
- **Environment variables**: none new — all tunables (batch size, flush interval, drop-oldest threshold) are Python constants with sensible defaults. Revisit when we have a reason to tune.

## Design Principles (refined via party-mode 2026-04-18)

- **Bounded hot-path cost.** The writer never blocks the request thread. Two failure modes, both handled: (a) producer-side overload → queue-full → drop-oldest + increment a counter; (b) consumer-side failure → DB unreachable or INSERT error → catch, log at ERROR with the failed batch size, continue. Neither path surfaces an exception to the request / task. Sample-loss counter is logged at WARNING every minute.
- **Cardinality safety.** `normalized_path` comes from `request.scope["route"].path` — the template. UUIDs never appear. If `request.scope["route"]` is `None` (404 / no route match / static file), the sample is **skipped**, not written with a `"UNMATCHED"` label; these are noise for the "slow endpoints" view.
- **Query-time over write-time.** No materialized views, no rollup tables. `percentile_cont` directly on the sample table. Backed by `(created_at DESC, normalized_path)` and `(created_at DESC, task_name)` indexes. If a single CTE with `generate_series`-bucketing + `percentile_cont` turns out unwieldy in practice, two round-trips (percentile query + sparkline query) is also fine — NFR50 (<300ms at 10M rows) is the contract, not the query shape.
- **Retention over scale engineering.** 30-day prune keeps tables small enough that partitioning is unneeded at <50-user scale. If prod ever crosses the NFR51 ceiling (~2 GB combined), retention tightens to 14d before any partitioning / downsampling work is considered.
- **Same admin shell, no new primitives.** `AdminMetricsScreen` mirrors `AdminErrorsScreen`; no new nav pattern, no new theme. Sparkline widget is bespoke via `CustomPainter` to avoid pulling in a chart library for one use case.
- **Freshness visible.** The page shows "Last updated Xs ago" in the header so the admin knows whether they're looking at cached or live data. Ties pull-to-refresh to a visible affordance.
- **Retry-safe Celery capture.** `task_prerun` start-times live in a thread-local dict keyed by `(task_name, task_id)` with a 10-minute TTL cleanup, not on task context. A retry is captured as a second lifecycle with `status="retry"`; no start-time collisions.
- **Graceful shutdown.** FastAPI lifespan and Celery `worker_shutdown` signal both drain the writer queue. Drain completes ≤5s on ECS SIGTERM (30s grace window before SIGKILL leaves ~6× safety margin).

### Locked decisions (propagate to sibling epic)

- Both this epic and `epic-user-feedback` extend `GET /v1/admin/stats`. Second epic to merge rebases its stats-response shape to union the first's fields.
- `require_admin` is the server guard; `isAdminProvider` the Flutter guard. No new gating primitives.
- Audit rows go to `error_logs` with `service="audit"` + a structured `error_message`. No new audit table.

## File Structure

Anticipated touched / new paths:

**Backend:**

```
services/migrator/migrations/versions/<ts>_add_latency_tables.py          (new)
services/api/src/middleware/latency_capture.py                            (new)
services/api/src/api/v1/admin/get_endpoint_metrics.py                     (new)
services/api/src/api/v1/admin/get_task_metrics.py                         (new)
services/api/src/api/v1/admin/get_stats.py                                (modify)
services/api/src/routers/v1/admin_router.py                               (modify — register 2 endpoints)
services/api/src/main.py                                                  (modify — register middleware + shutdown drain)
libraries/utils/utils/models/request_latency.py                           (new)
libraries/utils/utils/models/task_latency.py                              (new)
libraries/utils/utils/services/observability/__init__.py                  (new)
libraries/utils/utils/services/observability/batched_latency_writer.py    (new)
libraries/utils/utils/services/observability/celery_hooks.py              (new)
libraries/utils/utils/services/celery.py                                  (modify — register hooks + beat task)
libraries/utils/utils/tasks/observability_tasks/__init__.py               (new)
libraries/utils/utils/tasks/observability_tasks/cleanup_latency_samples.py (new)
services/api/tests/test_admin_metrics.py                                  (new)
libraries/utils/tests/test_batched_latency_writer.py                      (new)
libraries/utils/tests/test_celery_latency_hooks.py                        (new)
```

**Frontend:**

```
app/lib/features/admin/admin_metrics_screen.dart                          (new)
app/lib/features/admin/admin_dashboard_screen.dart                        (modify — add card + top stats)
app/lib/features/admin/widgets/latency_sparkline.dart                     (new)
app/lib/features/admin/widgets/metrics_table.dart                         (new)
app/lib/features/admin/models/metric_row.dart                             (new)
app/lib/features/admin/providers/metrics_provider.dart                    (new)
app/lib/core/services/api_client.dart                                     (modify — 2 methods)
app/lib/core/router/app_router.dart                                       (modify — 1 route)
app/test/features/admin/admin_metrics_screen_test.dart                    (new)
```

## Stories

**`obs-latency-1-backend-schema-and-writer`** — Migration + models + `BatchedLatencyWriter` + Celery hooks + FastAPI middleware. No API surface yet; this story wires up capture end-to-end and lands samples in the database. Verifiable via hitting any endpoint and seeing rows appear in `request_latencies`, and by queuing any Celery task and seeing rows appear in `task_latencies`.

ACs:
- Migration creates `request_latencies` + `task_latencies` with the schema and indexes documented in the architecture addendum (2026-04-18).
- `BatchedLatencyWriter` unit tests cover: enqueue under load, drop-oldest on queue-full, flush-by-count (100), flush-by-timer (2s), drain on SIGTERM, drop-count logging, **DB-insert-failure path (catches, logs, does not raise)**.
- FastAPI middleware skips `/health` and `/ready`, **skips when `request.scope["route"]` is None (unmatched route / static)**, never raises from the hot path, uses `request.scope["route"].path` for normalization.
- Celery signal handlers write one row per task lifecycle with correct status (`success` / `failure` / `retry`). **Retry test: a task that fails-then-succeeds produces two rows (`retry` then `success`), both with correct non-zero `duration_ms`.** Start-times live in a thread-local dict keyed by `(task_name, task_id)` with cleanup; no cross-task leakage verified in test.
- Hitting the app with 100 requests and letting 2s pass produces ≤100 rows in `request_latencies` (100 exact unless drop-oldest fired).
- NFR49 verified: microbenchmark shows ≤1ms P95 added to a baseline `GET /v1/user/me`.
- FastAPI lifespan `shutdown` drains the writer queue; Celery `worker_shutdown` signal drains the worker-side writer. Both complete within 5s in the integration test.

**`obs-latency-2-aggregation-endpoints-and-stats`** — Two aggregation endpoints + extend `/admin/stats` + register in `admin_router.py`.

ACs:
- `GET /v1/admin/metrics/endpoints?window=24h` returns one row per `(method, normalized_path)` with p50/p95/p99/count/error_rate + 24-bucket sparkline. Sorted by p95 desc.
- `GET /v1/admin/metrics/tasks?window=24h` returns the same shape for tasks with `failure_rate`.
- Both endpoints reject non-admin users with 403 via `require_admin` dependency.
- Both endpoints support `window` ∈ `{1h, 24h, 7d}`; invalid value → 400.
- `/admin/stats` response includes `overall_p95_ms` + `slowest_endpoint` (nullable — null on cold start).
- NFR50 verified: seeded dataset of 1M rows, 7d window, query plan captured in the test output, P95 <300ms on `db.t4g.micro` (local Postgres is fine for query-plan verification).
- Empty-dataset case: all endpoints return well-formed empty results, no 500.
- Audit: feedback status-change path is out of scope here (covered in the feedback epic).

**`obs-latency-3-flutter-metrics-screen`** — `AdminMetricsScreen` + sparkline widget + metrics table widget + dashboard card + dashboard top stats + router entry.

ACs:
- `/admin/metrics` renders when `isAdminProvider` is true; non-admin sees 404.
- Window selector (1h / 24h / 7d) defaults to 24h; changing it re-queries.
- Endpoints and Tasks tables render with correct column order, sparkline per row, sortable by any column (default p95 desc).
- Pull-to-refresh reloads both sections; the page header shows "Last updated Xs ago" that ticks in real time and resets on refresh.
- Dashboard gains "Overall p95 (24h)" + "Slowest endpoint" tiles and a "Metrics" card linking to `/admin/metrics`.
- Empty state renders when backend returns zero rows.
- Sparkline handles all-zero, single-spike, monotonically-increasing, and gap-of-zero patterns without visual glitches.
- Accessibility: percentile columns are readable by VoiceOver; sparklines have a textual label ("sparkline showing …"). WCAG AA color contrast on sparkline stroke.
- Widget test covers: cold load shimmer, populated table, empty state, error state.

**`obs-latency-4-nightly-prune-and-ops-readiness`** — Nightly prune beat task + documentation + ops runbook entry. (Shutdown drain is owned by story 1.)

ACs:
- `cleanup_latency_samples` runs at 02:00 UTC, deletes rows >30d from both tables. Unit test via frozen time.
- Beat schedule registration verified in `celery.py`.
- `docs/OBSERVABILITY.md` created with: how the capture works, query examples for ad-hoc SQL, retention policy, how to verify no sample loss (grep the WARNING log), escalation path if combined table size exceeds 2 GB (tighten to 14d retention).
- `BUGS.md` gets a one-line entry explaining that latency data is visible at `/admin/metrics` (future bug-triage entry point).
- Manual chaos verification documented: take the DB briefly unreachable, hit the API, confirm the writer logs ERROR, confirm no request is failed by the middleware, confirm capture resumes once DB is back.

## Dependencies

- **Blocks nothing** — this epic is a leaf observability capability.
- **Blocked by nothing** — all primitives (admin dashboard, Celery beat schedule, `require_admin`, `ErrorLog` audit pattern) already exist.
- **Parallelizable with** `epic-user-feedback` — they touch different tables and different admin screens; backend changes are in separate handler directories. Both can be dev'd concurrently.
- **Shares with `epic-user-feedback`**: both extend `GET /v1/admin/stats`. If scheduling is concurrent, the second epic to land must rebase on the first's stats-shape change. Not hard, but worth calling out.

## Open Questions for the User

- None at draft time — all questions were resolved in the 2026-04-18 user batch. Any emerge in Phase 6, I'll surface them there.
