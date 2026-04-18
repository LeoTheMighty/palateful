"""Unit tests for BatchedLatencyWriter.

100% coverage is the bar — this is the load-bearing piece. Tests cover:
  - enqueue under load + flush-by-count
  - flush-by-timer
  - drop-oldest when queue is full
  - dropped-count logging throttling
  - drain() on shutdown flushes remaining samples
  - DB-insert failure path catches, logs, does not raise
  - module-level singletons return the same instance + reset_for_tests
"""

from __future__ import annotations

import logging
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from utils.services.observability import batched_latency_writer as blw_mod
from utils.services.observability.batched_latency_writer import (
    BatchedLatencyWriter,
    get_request_writer,
    get_task_writer,
    reset_for_tests,
)


class _FakeDB:
    """A minimal fake Database that records the rows we would have INSERTed."""

    def __init__(self):
        self.executed: list[list[dict]] = []
        self.commits = 0
        self.closed = False
        self.db = SimpleNamespace(
            execute=self._execute,
            commit=self._commit,
        )

    def _execute(self, _stmt, rows):
        self.executed.append(list(rows))

    def _commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


from utils.models.request_latency import RequestLatency as _Model  # noqa: E402


def _factory(db: _FakeDB):
    def _make():
        return db
    return _make


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Keep module-level singletons from leaking between tests."""
    reset_for_tests()
    yield
    reset_for_tests()


# ----------------------------------------------------------------------
# enqueue + flush
# ----------------------------------------------------------------------


def test_flush_by_count():
    db = _FakeDB()
    writer = BatchedLatencyWriter(
        _Model,
        flush_batch_size=10,
        flush_interval_seconds=5.0,  # long — force count-based flush
        database_factory=_factory(db),
    )
    writer.start()
    for i in range(10):
        writer.enqueue({"i": i})
    # Wait up to 2 s for the flush to land.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not db.executed:
        time.sleep(0.01)
    writer.drain(timeout_seconds=1.0)

    assert db.executed, "batch should have flushed"
    total = sum(len(batch) for batch in db.executed)
    assert total == 10
    assert db.commits >= 1
    assert db.closed is True


def test_flush_by_timer():
    db = _FakeDB()
    writer = BatchedLatencyWriter(
        _Model,
        flush_batch_size=1000,  # huge — can only flush via timer
        flush_interval_seconds=0.05,
        database_factory=_factory(db),
    )
    writer.start()
    writer.enqueue({"i": 1})
    time.sleep(0.2)  # > flush_interval
    writer.drain(timeout_seconds=1.0)

    assert db.executed, "timer-based flush should have happened"
    total = sum(len(batch) for batch in db.executed)
    assert total == 1


# ----------------------------------------------------------------------
# drop-oldest
# ----------------------------------------------------------------------


def test_drop_oldest_on_queue_full():
    # Writer *not started* — queue fills synchronously, making the test
    # deterministic without chasing a racing background thread.
    writer = BatchedLatencyWriter(
        _Model,
        flush_batch_size=100,
        flush_interval_seconds=5.0,
        queue_max_size=3,
        database_factory=_factory(_FakeDB()),
    )
    for i in range(5):
        writer.enqueue({"i": i})
    # Dropped counter should reflect the 2 overflows (5 - 3).
    assert writer.total_dropped == 2
    # Queue should hold the 3 most recent samples (2, 3, 4).
    remaining: list[dict] = []
    while True:
        try:
            remaining.append(writer._queue.get_nowait())  # noqa: SLF001
        except Exception:
            break
    assert len(remaining) == 3
    kept = {s["i"] for s in remaining}
    assert 4 in kept, "newest sample must be retained"


def test_drop_count_logged_throttled(caplog):
    writer = BatchedLatencyWriter(
        _Model,
        queue_max_size=1,
        database_factory=_factory(_FakeDB()),
    )
    with caplog.at_level(
        logging.WARNING,
        logger="utils.services.observability.batched_latency_writer",
    ):
        for i in range(5):
            writer.enqueue({"i": i})
    drop_logs = [
        r for r in caplog.records
        if "dropped" in r.getMessage() and "samples" in r.getMessage()
    ]
    # We hit 4 overflows but the logger is throttled to at most once per
    # DROP_LOG_INTERVAL_SECONDS → expect exactly one WARN.
    assert len(drop_logs) == 1


# ----------------------------------------------------------------------
# DB-insert failure path
# ----------------------------------------------------------------------


def test_flush_swallows_db_errors(caplog):
    def _raising_factory():
        raise RuntimeError("DB unreachable")

    writer = BatchedLatencyWriter(
        _Model,
        flush_batch_size=2,
        flush_interval_seconds=0.02,
        database_factory=_raising_factory,
    )
    writer.start()
    with caplog.at_level(
        logging.ERROR,
        logger="utils.services.observability.batched_latency_writer",
    ):
        writer.enqueue({"i": 1})
        writer.enqueue({"i": 2})
        time.sleep(0.15)  # give the flush a couple tries
        writer.drain(timeout_seconds=1.0)

    # Must have logged AT LEAST ONCE and NOT raised.
    assert any(
        "failed to flush" in r.getMessage().lower() for r in caplog.records
    ), "flush failure must be logged"


def test_flush_swallows_commit_errors():
    db = _FakeDB()
    db.db.commit = MagicMock(side_effect=RuntimeError("boom"))

    writer = BatchedLatencyWriter(
        _Model,
        flush_batch_size=1,
        flush_interval_seconds=0.02,
        database_factory=_factory(db),
    )
    writer.start()
    writer.enqueue({"i": 1})
    time.sleep(0.1)
    # drain must complete — a raising commit must not hang shutdown.
    writer.drain(timeout_seconds=1.0)


# ----------------------------------------------------------------------
# drain / shutdown
# ----------------------------------------------------------------------


def test_drain_flushes_remaining_on_shutdown():
    db = _FakeDB()
    writer = BatchedLatencyWriter(
        _Model,
        flush_batch_size=1000,
        flush_interval_seconds=5.0,
        database_factory=_factory(db),
    )
    writer.start()
    for i in range(7):
        writer.enqueue({"i": i})
    writer.drain(timeout_seconds=2.0)

    total = sum(len(batch) for batch in db.executed)
    assert total == 7, "drain must flush all queued samples"


def test_drain_before_start_is_safe():
    # drain() before start() should not explode; it should flush
    # any pre-queued items synchronously.
    db = _FakeDB()
    writer = BatchedLatencyWriter(
        _Model,
        flush_batch_size=10,
        flush_interval_seconds=5.0,
        database_factory=_factory(db),
    )
    writer.enqueue({"i": 1})
    writer.drain(timeout_seconds=1.0)
    total = sum(len(batch) for batch in db.executed)
    assert total == 1


# ----------------------------------------------------------------------
# concurrent producers
# ----------------------------------------------------------------------


def test_thread_safe_enqueue():
    db = _FakeDB()
    writer = BatchedLatencyWriter(
        _Model,
        flush_batch_size=1000,
        flush_interval_seconds=0.05,
        database_factory=_factory(db),
    )
    writer.start()

    def _produce(n):
        for _ in range(n):
            writer.enqueue({"x": 1})

    threads = [threading.Thread(target=_produce, args=(50,)) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    writer.drain(timeout_seconds=2.0)

    total = sum(len(batch) for batch in db.executed)
    assert total == 500, "must not lose samples under 10-thread contention"


# ----------------------------------------------------------------------
# Module-level singletons
# ----------------------------------------------------------------------


def test_singletons_are_shared(monkeypatch):
    # Patch Database to avoid hitting the real DB during init; we don't
    # actually flush in this test (no enqueue).
    monkeypatch.setattr(blw_mod, "Database", _FakeDB)

    a = get_request_writer()
    b = get_request_writer()
    assert a is b

    c = get_task_writer()
    d = get_task_writer()
    assert c is d
    assert a is not c
