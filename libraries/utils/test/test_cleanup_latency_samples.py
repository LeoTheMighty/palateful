"""Unit tests for CleanupLatencySamplesTask (obs-latency-4)."""

from __future__ import annotations

from unittest.mock import MagicMock

from utils.tasks.observability_tasks.cleanup_latency_samples import (
    RETENTION_DAYS,
    CleanupLatencySamplesTask,
)


def _database_with_counts(request_count: int, task_count: int):
    """Build a Database mock whose two query chains return supplied counts."""

    request_chain = MagicMock()
    request_chain.filter.return_value = request_chain
    request_chain.count.return_value = request_count
    request_chain.delete.return_value = request_count

    task_chain = MagicMock()
    task_chain.filter.return_value = task_chain
    task_chain.count.return_value = task_count
    task_chain.delete.return_value = task_count

    db = MagicMock()
    # First query is RequestLatency, second is TaskLatency — match in order.
    db.query.side_effect = [request_chain, task_chain]
    db.commit = MagicMock()

    database = MagicMock()
    database.db = db
    return database, request_chain, task_chain


def _make_task(database):
    task = CleanupLatencySamplesTask()
    task.database = database
    return task


def test_deletes_rows_older_than_retention():
    database, request_chain, task_chain = _database_with_counts(
        request_count=17, task_count=4,
    )
    task = _make_task(database)
    result = task.execute()

    assert result["success"] is True
    assert result["data"]["request_deleted_count"] == 17
    assert result["data"]["task_deleted_count"] == 4
    request_chain.delete.assert_called_once()
    task_chain.delete.assert_called_once()
    assert database.db.commit.call_count == 2


def test_no_rows_to_delete_is_a_noop():
    database, request_chain, task_chain = _database_with_counts(
        request_count=0, task_count=0,
    )
    task = _make_task(database)
    result = task.execute()

    assert result["data"]["request_deleted_count"] == 0
    assert result["data"]["task_deleted_count"] == 0
    request_chain.delete.assert_not_called()
    task_chain.delete.assert_not_called()
    database.db.commit.assert_not_called()


def test_task_name_registered_for_beat_schedule():
    # Beat schedule entry in celery.py references the task by this name;
    # keep the test so a rename stays linked to the schedule update.
    assert CleanupLatencySamplesTask.name == "cleanup_latency_samples"


def test_retention_matches_architecture_contract():
    # Architecture addendum 2026-04-18 fixes retention at 30 days.
    assert RETENTION_DAYS == 30
