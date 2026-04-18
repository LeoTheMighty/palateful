"""Batched async writer for high-frequency latency capture.

Singleton-per-process primitive that buffers latency samples on a bounded
queue and flushes them in bulk to Postgres. The hot path (middleware /
Celery signal) only calls `enqueue()`, which never blocks and never raises
— even when the queue is saturated or the database is unreachable.

Design (per architecture addendum 2026-04-18):
  - `queue.Queue` (thread-safe) holds dicts, bounded to avoid unbounded
    memory growth.
  - A daemon thread consumes the queue in batches of up to
    ``FLUSH_BATCH_SIZE`` samples, flushing whichever comes first between
    that threshold and a ``FLUSH_INTERVAL_SECONDS`` timer.
  - Queue-full policy is **drop-oldest, never block** — the hot path must
    not wait on the writer. Dropped-count is logged every
    ``DROP_LOG_INTERVAL_SECONDS`` so sample loss is observable.
  - Flush errors are caught and logged; the batch is dropped and the
    writer loop continues.
  - ``drain()`` blocks up to ``drain_timeout_seconds`` to flush any
    remaining samples on shutdown — wired to FastAPI lifespan shutdown and
    Celery ``worker_shutdown`` signal.

Two module-level singletons (``_request_writer``, ``_task_writer``) keep
the process-wide state simple; callers use ``get_request_writer()`` /
``get_task_writer()`` rather than instantiating directly.
"""

from __future__ import annotations

import contextlib
import logging
import queue
import threading
import time
from typing import Any

from sqlalchemy import insert

from utils.models.request_latency import RequestLatency
from utils.models.task_latency import TaskLatency
from utils.services.database import Database

logger = logging.getLogger(__name__)

# Flush thresholds — Python constants intentionally, no env vars (see epic).
FLUSH_BATCH_SIZE = 100
FLUSH_INTERVAL_SECONDS = 2.0
QUEUE_MAX_SIZE = 10_000
DROP_LOG_INTERVAL_SECONDS = 60.0
DEFAULT_DRAIN_TIMEOUT_SECONDS = 5.0


class BatchedLatencyWriter:
    """Single-table batched latency writer.

    One instance per target table. Thread-safe — ``enqueue()`` can be
    called concurrently from any number of FastAPI request handlers or
    Celery signal handlers.

    Not started until ``start()`` is invoked (so importing the module is
    side-effect-free; tests don't spin up threads on import).
    """

    def __init__(
        self,
        model_class: type,
        *,
        flush_batch_size: int = FLUSH_BATCH_SIZE,
        flush_interval_seconds: float = FLUSH_INTERVAL_SECONDS,
        queue_max_size: int = QUEUE_MAX_SIZE,
        database_factory=Database,
    ):
        self._model_class = model_class
        self._flush_batch_size = flush_batch_size
        self._flush_interval_seconds = flush_interval_seconds
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(
            maxsize=queue_max_size
        )
        self._database_factory = database_factory
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        # Separate counters: `_total_dropped` is append-only for
        # observability assertions; `_drops_since_log` resets on each
        # emitted WARNING to throttle log volume.
        self._total_dropped = 0
        self._drops_since_log = 0
        self._dropped_count_lock = threading.Lock()
        self._last_drop_log_at = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background flush thread if not already running."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"BatchedLatencyWriter[{self._model_class.__tablename__}]",
            daemon=True,
        )
        self._thread.start()

    def drain(self, timeout_seconds: float = DEFAULT_DRAIN_TIMEOUT_SECONDS) -> None:
        """Flush any buffered samples and stop the background thread.

        Safe to call multiple times. On timeout, remaining samples are
        dropped — we prefer losing the last 2 s of samples over hanging
        shutdown past the container grace window (ECS SIGTERM gives 30 s;
        our default timeout is 5 s for a 6× margin).
        """
        if self._thread is None:
            # Writer never started — flush synchronously (tests).
            self._flush_all_sync()
            return

        self._stop_event.set()
        self._thread.join(timeout=timeout_seconds)
        if self._thread.is_alive():
            logger.warning(
                "BatchedLatencyWriter[%s] did not drain within %.1fs; "
                "dropping remaining samples.",
                self._model_class.__tablename__,
                timeout_seconds,
            )

    # ------------------------------------------------------------------
    # Hot path
    # ------------------------------------------------------------------

    def enqueue(self, sample: dict[str, Any]) -> None:
        """Add a sample to the queue. Never blocks, never raises.

        On queue-full: drop the oldest sample (make room for the newest)
        and bump the dropped counter. Log the counter at most once per
        ``DROP_LOG_INTERVAL_SECONDS``.
        """
        try:
            self._queue.put_nowait(sample)
        except queue.Full:
            # Drop-oldest: consume one, then retry. If retry also fails
            # (other producers raced us), give up silently — the point is
            # to not block.
            with self._dropped_count_lock:
                self._total_dropped += 1
                self._drops_since_log += 1
            with contextlib.suppress(queue.Empty):
                self._queue.get_nowait()
            with contextlib.suppress(queue.Full):
                self._queue.put_nowait(sample)
            self._maybe_log_dropped()

    @property
    def total_dropped(self) -> int:
        """Cumulative dropped-sample count since process start."""
        with self._dropped_count_lock:
            return self._total_dropped

    def _maybe_log_dropped(self) -> None:
        """Log drop count at most once per DROP_LOG_INTERVAL_SECONDS."""
        now = time.monotonic()
        with self._dropped_count_lock:
            if self._last_drop_log_at != 0.0 and (
                now - self._last_drop_log_at < DROP_LOG_INTERVAL_SECONDS
            ):
                return
            count = self._drops_since_log
            if count == 0:
                return
            self._drops_since_log = 0
            self._last_drop_log_at = now
        logger.warning(
            "BatchedLatencyWriter[%s] dropped %d samples in the last "
            "~%.0fs due to queue saturation",
            self._model_class.__tablename__,
            count,
            DROP_LOG_INTERVAL_SECONDS,
        )

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Consume the queue and flush batches until stopped."""
        while not self._stop_event.is_set():
            batch = self._collect_batch()
            if batch:
                self._flush(batch)
        # Final drain on shutdown — gather everything still queued.
        self._flush_all_sync()

    def _collect_batch(self) -> list[dict[str, Any]]:
        """Block up to ``flush_interval`` waiting for a sample; then drain
        the queue non-blockingly until we hit ``flush_batch_size``.
        """
        batch: list[dict[str, Any]] = []
        deadline = time.monotonic() + self._flush_interval_seconds
        try:
            first = self._queue.get(timeout=self._flush_interval_seconds)
            batch.append(first)
        except queue.Empty:
            return batch

        while len(batch) < self._flush_batch_size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _flush_all_sync(self) -> None:
        """Drain the queue and flush in batches without blocking on time."""
        while True:
            batch: list[dict[str, Any]] = []
            try:
                while len(batch) < self._flush_batch_size:
                    batch.append(self._queue.get_nowait())
            except queue.Empty:
                pass
            if not batch:
                return
            self._flush(batch)

    def _flush(self, batch: list[dict[str, Any]]) -> None:
        """Bulk-INSERT a batch of samples. Catches all errors + logs."""
        if not batch:
            return
        try:
            database = self._database_factory()
            try:
                database.db.execute(insert(self._model_class), batch)
                database.db.commit()
            finally:
                database.close()
        except Exception:
            # Never let the capture path raise. Log once with the batch
            # size so operators can see if loss is correlated with load.
            logger.exception(
                "BatchedLatencyWriter[%s] failed to flush %d samples; "
                "batch dropped.",
                self._model_class.__tablename__,
                len(batch),
            )


# --------------------------------------------------------------------------
# Module-level singletons — one writer per target table, one process-wide.
# --------------------------------------------------------------------------

_request_writer: BatchedLatencyWriter | None = None
_task_writer: BatchedLatencyWriter | None = None
_singleton_lock = threading.Lock()


def get_request_writer() -> BatchedLatencyWriter:
    """Return the process-wide request-latency writer (start on first use)."""
    global _request_writer
    with _singleton_lock:
        if _request_writer is None:
            _request_writer = BatchedLatencyWriter(RequestLatency)
            _request_writer.start()
        return _request_writer


def get_task_writer() -> BatchedLatencyWriter:
    """Return the process-wide task-latency writer (start on first use)."""
    global _task_writer
    with _singleton_lock:
        if _task_writer is None:
            _task_writer = BatchedLatencyWriter(TaskLatency)
            _task_writer.start()
        return _task_writer


def reset_for_tests() -> None:
    """Reset singletons — tests only. Draining is best-effort."""
    global _request_writer, _task_writer
    with _singleton_lock:
        for writer in (_request_writer, _task_writer):
            if writer is not None:
                with contextlib.suppress(Exception):
                    writer.drain(timeout_seconds=1.0)
        _request_writer = None
        _task_writer = None
