"""Unit tests for CleanupLatencySamplesTask (obs-latency-4 + cla-1a)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from utils.tasks.observability_tasks.cleanup_latency_samples import (
    RETENTION_DAYS,
    CleanupLatencySamplesTask,
)


def _database_with_counts(
    request_count: int,
    task_count: int,
    client_count: int = 0,
):
    """Build a Database mock whose three query chains return supplied counts."""

    request_chain = MagicMock()
    request_chain.filter.return_value = request_chain
    request_chain.count.return_value = request_count
    request_chain.delete.return_value = request_count

    task_chain = MagicMock()
    task_chain.filter.return_value = task_chain
    task_chain.count.return_value = task_count
    task_chain.delete.return_value = task_count

    client_chain = MagicMock()
    client_chain.filter.return_value = client_chain
    client_chain.count.return_value = client_count
    client_chain.delete.return_value = client_count

    db = MagicMock()
    # Match prune order: RequestLatency, TaskLatency, ClientLatency.
    db.query.side_effect = [request_chain, task_chain, client_chain]
    db.commit = MagicMock()

    database = MagicMock()
    database.db = db
    return database, request_chain, task_chain, client_chain


def _make_task(database):
    task = CleanupLatencySamplesTask()
    task.database = database
    return task


def test_deletes_rows_older_than_retention():
    database, request_chain, task_chain, client_chain = _database_with_counts(
        request_count=17, task_count=4, client_count=123,
    )
    task = _make_task(database)
    # Force day != 1 so VACUUM is skipped and the DB mock isn't hit with it.
    with patch(
        "utils.tasks.observability_tasks.cleanup_latency_samples.datetime"
    ) as mock_dt:
        mock_dt.utcnow.return_value = datetime(2026, 4, 23, 2, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = task.execute()

    assert result["success"] is True
    assert result["data"]["request_deleted_count"] == 17
    assert result["data"]["task_deleted_count"] == 4
    assert result["data"]["client_deleted_count"] == 123
    assert result["data"]["vacuum_ran"] is False
    request_chain.delete.assert_called_once()
    task_chain.delete.assert_called_once()
    client_chain.delete.assert_called_once()
    assert database.db.commit.call_count == 3


def test_no_rows_to_delete_is_a_noop():
    database, request_chain, task_chain, client_chain = _database_with_counts(
        request_count=0, task_count=0, client_count=0,
    )
    task = _make_task(database)
    with patch(
        "utils.tasks.observability_tasks.cleanup_latency_samples.datetime"
    ) as mock_dt:
        mock_dt.utcnow.return_value = datetime(2026, 4, 23, 2, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = task.execute()

    assert result["data"]["request_deleted_count"] == 0
    assert result["data"]["task_deleted_count"] == 0
    assert result["data"]["client_deleted_count"] == 0
    request_chain.delete.assert_not_called()
    task_chain.delete.assert_not_called()
    client_chain.delete.assert_not_called()
    database.db.commit.assert_not_called()


def test_monthly_vacuum_runs_on_first_of_month():
    """Day == 1 triggers VACUUM ANALYZE on all three latency tables."""
    database, *_ = _database_with_counts(
        request_count=0, task_count=0, client_count=0,
    )

    # Wire up a raw_connection chain the task can drive through the
    # VACUUM sequence (autocommit + cursor + execute + close).
    raw_conn = MagicMock()
    raw_conn.isolation_level = 1  # arbitrary pre-existing value
    cursor = MagicMock()
    raw_conn.cursor.return_value = cursor
    engine = MagicMock()
    engine.raw_connection.return_value = raw_conn
    database.db.get_bind.return_value = engine

    task = _make_task(database)
    with patch(
        "utils.tasks.observability_tasks.cleanup_latency_samples.datetime"
    ) as mock_dt:
        mock_dt.utcnow.return_value = datetime(2026, 5, 1, 2, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = task.execute()

    assert result["data"]["vacuum_ran"] is True
    raw_conn.set_isolation_level.assert_any_call(0)  # AUTOCOMMIT
    # Three VACUUM ANALYZE calls — one per table.
    executed = [call.args[0] for call in cursor.execute.call_args_list]
    assert executed == [
        "VACUUM ANALYZE request_latencies",
        "VACUUM ANALYZE task_latencies",
        "VACUUM ANALYZE client_latencies",
    ]
    # Isolation is restored to the prior value.
    raw_conn.set_isolation_level.assert_called_with(1)
    raw_conn.close.assert_called_once()


def test_vacuum_skipped_on_non_first_of_month():
    """Ensure VACUUM is NOT issued when day != 1."""
    database, *_ = _database_with_counts(
        request_count=0, task_count=0, client_count=0,
    )
    database.db.get_bind = MagicMock()  # should never be called

    task = _make_task(database)
    with patch(
        "utils.tasks.observability_tasks.cleanup_latency_samples.datetime"
    ) as mock_dt:
        mock_dt.utcnow.return_value = datetime(2026, 4, 23, 2, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        task.execute()

    database.db.get_bind.assert_not_called()


def test_task_name_registered_for_beat_schedule():
    # Beat schedule entry in celery.py references the task by this name;
    # keep the test so a rename stays linked to the schedule update.
    assert CleanupLatencySamplesTask.name == "cleanup_latency_samples"


def test_retention_matches_architecture_contract():
    # Architecture addendum 2026-04-18 fixes retention at 30 days.
    # cla-1a adopts the same window for client_latencies.
    assert RETENTION_DAYS == 30
