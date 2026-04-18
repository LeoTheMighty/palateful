# Story obs-latency-1: Backend schema + BatchedLatencyWriter + capture middleware/hooks

**Status:** done
**Epic:** epic-observability-latency

## Goal
Land end-to-end latency capture in Postgres. Create the two append-only tables
(`request_latencies`, `task_latencies`), the `BatchedLatencyWriter` primitive
that flushes batched samples off the hot path, the FastAPI middleware that
enqueues one sample per request, and the Celery signal handlers that enqueue
one sample per task lifecycle. No API surface yet — aggregation endpoints land
in obs-latency-2.

## Scope (from epic)
- Migration creates `request_latencies` + `task_latencies` per the architecture
  addendum (2026-04-18) with the documented indexes.
- New `BatchedLatencyWriter` lives in
  `libraries/utils/utils/services/observability/batched_latency_writer.py` as
  a thread-backed singleton per process. Flushes on 100 samples, 2 s timer, or
  explicit drain. Drop-oldest on queue-full. DB-insert failure path catches,
  logs, continues.
- FastAPI middleware in `services/api/src/middleware/latency_capture.py`
  registered after `ErrorTrackingMiddleware`. Skips `/health` and `/ready`.
  Skips when `request.scope["route"]` is None. Uses the route template for
  path normalization. Never raises from the hot path.
- Celery signal handlers in
  `libraries/utils/utils/services/observability/celery_hooks.py`. `task_prerun`
  stores start-time in a TTL-bounded dict keyed by `(task_name, task_id)`;
  `task_postrun` writes one `success`/`retry` sample; `task_failure` writes
  one `failure` sample.
- FastAPI lifespan `shutdown` drains the writer. Celery `worker_shutdown`
  signal drains the worker-side writer.

## File List
- `services/migrator/migrations/versions/20260418010000_add_latency_tables.py` — new
- `libraries/utils/utils/models/request_latency.py` — new
- `libraries/utils/utils/models/task_latency.py` — new
- `libraries/utils/utils/models/__init__.py` — modified (export)
- `libraries/utils/utils/services/observability/__init__.py` — new
- `libraries/utils/utils/services/observability/batched_latency_writer.py` — new
- `libraries/utils/utils/services/observability/celery_hooks.py` — new
- `libraries/utils/utils/services/celery.py` — modified (import hooks)
- `services/api/src/middleware/latency_capture.py` — new
- `services/api/src/main.py` — modified (register middleware + shutdown drain)
- `libraries/utils/test/test_batched_latency_writer.py` — new
- `libraries/utils/test/test_celery_latency_hooks.py` — new
- `services/api/tests/test_latency_capture_middleware.py` — new

## Notes
- Single thread-backed writer class (using `queue.Queue` + a daemon worker
  thread) serves both FastAPI and Celery. `put_nowait` is safe from
  asyncio code without blocking the event loop, and thread-safe for Celery
  signal handlers. This is simpler than maintaining two variants (asyncio +
  threading) and meets every AC.
- Drop-oldest policy implemented by peeking queue length and draining one
  sample before the put when full.
- `_start_times` dict in celery hooks uses a simple TTL (10 min default). On
  every prerun we also sweep expired entries so the dict stays bounded even
  if tasks crash before their postrun/failure handler fires.

## QA walkthrough
See `_bmad-output/implementation-artifacts/obs-latency-1-qa-walkthrough.md`.
