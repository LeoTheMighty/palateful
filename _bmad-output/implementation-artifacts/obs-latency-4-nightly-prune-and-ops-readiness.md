# Story obs-latency-4: Nightly prune + ops readiness

**Status:** done
**Epic:** epic-observability-latency

## Goal
Keep the latency tables bounded at 30 days and give the operator a
written runbook for the new capture path. Nightly Celery task runs at
02:00 UTC alongside `cleanup-error-logs`. Shutdown drain (both FastAPI
lifespan and Celery `worker_shutdown`) is already in story 1.

## Scope
- New task `cleanup_latency_samples` in
  `libraries/utils/utils/tasks/observability_tasks/`.
- Register in the Celery beat schedule
  (`libraries/utils/utils/services/celery.py`) at `crontab(hour=2, minute=0)`.
- New `docs/OBSERVABILITY.md` — capture architecture, ad-hoc query
  examples, retention + escalation policy, chaos verification steps.
- One-line entry in `BUGS.md` so triage work has a natural entry point.

## File List
- `libraries/utils/utils/tasks/observability_tasks/__init__.py` — new
- `libraries/utils/utils/tasks/observability_tasks/cleanup_latency_samples.py` — new
- `libraries/utils/utils/services/celery.py` — beat entry
- `libraries/utils/test/test_cleanup_latency_samples.py` — new
- `docs/OBSERVABILITY.md` — new
- `BUGS.md` — one-line entry
