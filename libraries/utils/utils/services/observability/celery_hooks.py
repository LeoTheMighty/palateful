"""Celery signal handlers that capture per-task latency.

Registers on import: the test against `task_prerun`/`task_postrun`/
`task_failure` + `worker_shutdown` signals fires for every Celery task,
writing one row per lifecycle outcome to `task_latencies` via the
`BatchedLatencyWriter`.

Lifecycle rules (per epic):
  - `task_prerun`   → stash start_time in a TTL-bounded dict keyed by
    `(task_name, task_id)`.
  - `task_postrun`  → compute duration, enqueue sample with status
    derived from the task state (`SUCCESS` → `success`, `RETRY` → `retry`,
    `FAILURE` → already handled by `task_failure`, skip).
  - `task_failure`  → compute duration, enqueue sample with
    `status='failure'`.
  - `worker_shutdown` → drain the task writer queue before process exit.

A task that fails-then-succeeds on retry produces two rows: a
`status='retry'` row at first failure and a `status='success'` row on the
successful retry. Start-time cleanup on both prerun (sweep expired) and
postrun/failure (pop the handled key) keeps the dict bounded even if a
handler fires unpaired due to crash or Celery quirks.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from celery.signals import task_failure, task_postrun, task_prerun, worker_shutdown

from utils.services.observability.batched_latency_writer import get_task_writer

logger = logging.getLogger(__name__)

# Entries older than this are swept on the next prerun — guards against
# unbounded growth if a task crashes before postrun/failure fires.
START_TIME_TTL_SECONDS = 600.0  # 10 minutes

# Dict keyed by (task_name, task_id) → (start_time_monotonic, recorded_at).
_start_times: dict[tuple[str, str], tuple[float, float]] = {}
_start_times_lock = threading.Lock()


def _sweep_expired(now: float) -> None:
    """Remove expired start-time entries. Caller holds the lock."""
    if not _start_times:
        return
    cutoff = now - START_TIME_TTL_SECONDS
    stale = [
        key for key, (_, recorded_at) in _start_times.items() if recorded_at < cutoff
    ]
    for key in stale:
        _start_times.pop(key, None)
    if stale:
        logger.debug(
            "Swept %d stale start-time entries from celery latency tracker",
            len(stale),
        )


def _record_start(task_name: str, task_id: str) -> None:
    """Store the start time for a task lifecycle."""
    now_monotonic = time.perf_counter()
    now_wall = time.time()
    with _start_times_lock:
        _sweep_expired(now_wall)
        _start_times[(task_name, task_id)] = (now_monotonic, now_wall)


def _pop_duration_ms(task_name: str, task_id: str) -> int | None:
    """Pop the recorded start time and return elapsed milliseconds."""
    with _start_times_lock:
        entry = _start_times.pop((task_name, task_id), None)
    if entry is None:
        return None
    start_monotonic, _ = entry
    return max(int((time.perf_counter() - start_monotonic) * 1000), 0)


def _enqueue_sample(
    task_name: str,
    task_id: str,
    duration_ms: int,
    status: str,
    queue_name: str | None,
) -> None:
    """Enqueue one task_latencies sample. Never raises from the hot path."""
    try:
        writer = get_task_writer()
        writer.enqueue(
            {
                "task_name": task_name,
                "task_id": task_id,
                "duration_ms": duration_ms,
                "status": status,
                "queue_name": queue_name,
            }
        )
    except Exception:
        # Capture path must never fail the task.
        logger.exception("Failed to enqueue task latency sample")


# --------------------------------------------------------------------------
# Celery signal handlers (registered on import via @signal.connect)
# --------------------------------------------------------------------------


@task_prerun.connect
def _on_task_prerun(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    **_kwargs: Any,
) -> None:
    """Stash the start time for a task."""
    task_name = _task_name(sender, task)
    if not task_name or not task_id:
        return
    _record_start(task_name, task_id)


@task_postrun.connect
def _on_task_postrun(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    state: str | None = None,
    **_kwargs: Any,
) -> None:
    """Write a sample for success/retry; skip failure (handled separately)."""
    task_name = _task_name(sender, task)
    if not task_name or not task_id:
        return

    # `state` is the celery task state: SUCCESS, RETRY, FAILURE, ...
    if state == "FAILURE":
        # task_failure handles this lifecycle — skip to avoid double-count.
        # But still pop so the dict doesn't leak.
        _pop_duration_ms(task_name, task_id)
        return

    duration_ms = _pop_duration_ms(task_name, task_id)
    if duration_ms is None:
        return

    status = "retry" if state == "RETRY" else "success"

    _enqueue_sample(
        task_name=task_name,
        task_id=task_id,
        duration_ms=duration_ms,
        status=status,
        queue_name=_queue_name(task),
    )


@task_failure.connect
def _on_task_failure(
    sender: Any = None,
    task_id: str | None = None,
    **_kwargs: Any,
) -> None:
    """Write a failure sample."""
    task_name = _task_name(sender, None)
    if not task_name or not task_id:
        return

    duration_ms = _pop_duration_ms(task_name, task_id)
    if duration_ms is None:
        return

    _enqueue_sample(
        task_name=task_name,
        task_id=task_id,
        duration_ms=duration_ms,
        status="failure",
        queue_name=_queue_name(sender),
    )


@worker_shutdown.connect
def _on_worker_shutdown(**_kwargs: Any) -> None:
    """Drain the task writer so the last 2s of samples aren't lost on deploy."""
    try:
        writer = get_task_writer()
        writer.drain()
    except Exception:
        logger.exception("Failed to drain task latency writer on shutdown")


# --------------------------------------------------------------------------
# Helpers — pull the task name + queue name from whatever celery gives us.
# --------------------------------------------------------------------------


def _task_name(sender: Any, task: Any) -> str | None:
    """Best-effort task name extraction from the signal kwargs."""
    for candidate in (task, sender):
        if candidate is None:
            continue
        name = getattr(candidate, "name", None)
        if isinstance(name, str) and name:
            return name
    if isinstance(sender, str):
        return sender
    return None


def _queue_name(task: Any) -> str | None:
    """Best-effort queue name extraction from a celery task object."""
    if task is None:
        return None
    request = getattr(task, "request", None)
    if request is None:
        return None
    queue_name = getattr(request, "delivery_info", None)
    if isinstance(queue_name, dict):
        value = queue_name.get("routing_key") or queue_name.get("exchange")
        if isinstance(value, str) and value:
            return value
    return None
