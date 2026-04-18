"""Unit tests for the Celery task-latency signal handlers.

We exercise the handlers directly (not via a real Celery worker) because
we just want to verify the bookkeeping: one sample per task lifecycle,
correct `status`, start-time dict bounded, no cross-task leakage.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from utils.services.observability import batched_latency_writer as blw_mod
from utils.services.observability import celery_hooks as hooks


class _SpyWriter:
    """Records enqueue()s so we can assert in tests."""

    def __init__(self):
        self.samples: list[dict] = []
        self.drained = False

    def enqueue(self, sample):
        self.samples.append(sample)

    def drain(self, timeout_seconds: float = 5.0):
        self.drained = True


@pytest.fixture(autouse=True)
def _fresh_writer(monkeypatch):
    """Replace the module-level task writer with a spy for each test."""
    spy = _SpyWriter()
    monkeypatch.setattr(hooks, "get_task_writer", lambda: spy)
    # Clear the start-time dict so tests don't leak into each other.
    hooks._start_times.clear()  # noqa: SLF001
    yield spy


def _task(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        request=SimpleNamespace(delivery_info={"routing_key": "celery"}),
    )


# ----------------------------------------------------------------------
# Happy path: success
# ----------------------------------------------------------------------


def test_prerun_postrun_success_writes_one_sample(_fresh_writer):
    task = _task("my.task")
    hooks._on_task_prerun(sender=task, task_id="tid-1", task=task)  # noqa: SLF001
    time.sleep(0.005)  # ensure duration > 0
    hooks._on_task_postrun(  # noqa: SLF001
        sender=task, task_id="tid-1", task=task, state="SUCCESS"
    )

    assert len(_fresh_writer.samples) == 1
    sample = _fresh_writer.samples[0]
    assert sample["task_name"] == "my.task"
    assert sample["task_id"] == "tid-1"
    assert sample["status"] == "success"
    assert sample["duration_ms"] >= 0
    assert sample["queue_name"] == "celery"


# ----------------------------------------------------------------------
# Retry lifecycle: prerun → postrun(state=RETRY), then prerun → postrun
# (state=SUCCESS) produces two rows, both with non-zero duration.
# ----------------------------------------------------------------------


def test_retry_then_success_writes_two_samples(_fresh_writer):
    task = _task("my.task")

    hooks._on_task_prerun(sender=task, task_id="tid-1", task=task)  # noqa: SLF001
    time.sleep(0.005)
    hooks._on_task_postrun(  # noqa: SLF001
        sender=task, task_id="tid-1", task=task, state="RETRY"
    )

    # Retry: celery fires a new prerun for the retry attempt.
    hooks._on_task_prerun(sender=task, task_id="tid-1", task=task)  # noqa: SLF001
    time.sleep(0.005)
    hooks._on_task_postrun(  # noqa: SLF001
        sender=task, task_id="tid-1", task=task, state="SUCCESS"
    )

    assert len(_fresh_writer.samples) == 2
    statuses = [s["status"] for s in _fresh_writer.samples]
    assert statuses == ["retry", "success"]
    assert all(s["duration_ms"] >= 0 for s in _fresh_writer.samples)


# ----------------------------------------------------------------------
# Failure lifecycle: task_failure fires, task_postrun fires with state=FAILURE.
# We expect exactly one sample with status="failure" (no double-count).
# ----------------------------------------------------------------------


def test_failure_writes_one_sample(_fresh_writer):
    task = _task("my.task")
    hooks._on_task_prerun(sender=task, task_id="tid-fail", task=task)  # noqa: SLF001
    time.sleep(0.005)
    # Celery fires task_failure first, then task_postrun with state=FAILURE.
    hooks._on_task_failure(sender=task, task_id="tid-fail")  # noqa: SLF001
    hooks._on_task_postrun(  # noqa: SLF001
        sender=task, task_id="tid-fail", task=task, state="FAILURE"
    )

    assert len(_fresh_writer.samples) == 1
    assert _fresh_writer.samples[0]["status"] == "failure"


# ----------------------------------------------------------------------
# No cross-task leakage.
# ----------------------------------------------------------------------


def test_two_tasks_no_crosstalk(_fresh_writer):
    task_a = _task("task.a")
    task_b = _task("task.b")
    hooks._on_task_prerun(sender=task_a, task_id="a-1", task=task_a)  # noqa: SLF001
    hooks._on_task_prerun(sender=task_b, task_id="b-1", task=task_b)  # noqa: SLF001
    hooks._on_task_postrun(  # noqa: SLF001
        sender=task_a, task_id="a-1", task=task_a, state="SUCCESS"
    )
    hooks._on_task_postrun(  # noqa: SLF001
        sender=task_b, task_id="b-1", task=task_b, state="SUCCESS"
    )

    names = sorted(s["task_name"] for s in _fresh_writer.samples)
    assert names == ["task.a", "task.b"]
    # Both dict entries should have been consumed.
    assert len(hooks._start_times) == 0  # noqa: SLF001


# ----------------------------------------------------------------------
# Start-time dict is TTL-bounded even when postrun never fires.
# ----------------------------------------------------------------------


def test_stale_start_times_swept_on_prerun(monkeypatch):
    monkeypatch.setattr(hooks, "START_TIME_TTL_SECONDS", 0.01)

    task = _task("my.task")
    hooks._on_task_prerun(sender=task, task_id="orphan", task=task)  # noqa: SLF001
    assert ("my.task", "orphan") in hooks._start_times  # noqa: SLF001

    # Sleep past TTL, then fire another prerun which triggers the sweep.
    time.sleep(0.05)
    hooks._on_task_prerun(sender=task, task_id="new", task=task)  # noqa: SLF001

    # "orphan" should have been swept; only the new entry should remain.
    assert ("my.task", "orphan") not in hooks._start_times  # noqa: SLF001
    assert ("my.task", "new") in hooks._start_times  # noqa: SLF001


# ----------------------------------------------------------------------
# Missing start time (handler fires unpaired) is a silent no-op.
# ----------------------------------------------------------------------


def test_postrun_without_prerun_is_noop(_fresh_writer):
    task = _task("my.task")
    hooks._on_task_postrun(  # noqa: SLF001
        sender=task, task_id="unknown", task=task, state="SUCCESS"
    )
    assert _fresh_writer.samples == []


# ----------------------------------------------------------------------
# worker_shutdown drains the writer.
# ----------------------------------------------------------------------


def test_worker_shutdown_drains(_fresh_writer):
    hooks._on_worker_shutdown()  # noqa: SLF001
    assert _fresh_writer.drained is True


# ----------------------------------------------------------------------
# Capture path never raises — if the writer blows up, the handler
# swallows the exception so celery task success/failure isn't affected.
# ----------------------------------------------------------------------


def test_enqueue_error_is_swallowed(monkeypatch):
    class _ExplodingWriter:
        def enqueue(self, _):
            raise RuntimeError("writer on fire")

    monkeypatch.setattr(hooks, "get_task_writer", lambda: _ExplodingWriter())

    task = _task("my.task")
    hooks._on_task_prerun(sender=task, task_id="tid", task=task)  # noqa: SLF001
    # Must not raise.
    hooks._on_task_postrun(  # noqa: SLF001
        sender=task, task_id="tid", task=task, state="SUCCESS"
    )
