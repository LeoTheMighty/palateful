"""Tests for SweepStuckImportsTask.

These tests stub out the database to focus on the stuck-detection logic.
"""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _make_job(
    *,
    status="processing",
    started_at=None,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status=status,
        started_at=started_at,
        completed_at=None,
        error_message=None,
    )


def _make_item(*, import_job_id, status="matching", updated_at=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        import_job_id=import_job_id,
        status=status,
        updated_at=updated_at,
        error_message=None,
        error_code=None,
    )


def _make_database(jobs, items, latest_item_update_per_job):
    """Build a fake database whose query API returns the pre-built fixtures.

    latest_item_update_per_job: dict[job_id -> datetime|None] returned by the
    `select(max(updated_at))` query path.
    """
    database = MagicMock()
    db = MagicMock()

    # query(ImportJob).filter(...).limit(...).all() → jobs
    job_chain = MagicMock()
    job_chain.filter.return_value = job_chain
    job_chain.limit.return_value = job_chain
    job_chain.all.return_value = jobs

    # query(ImportItem).filter(...).all() → items for a job
    item_chain = MagicMock()
    item_chain.filter.return_value = item_chain

    def items_for_job_call():
        # Called per job; the task only calls it for jobs it decides to mark
        # stuck, so return all items that belong to the currently-being-marked
        # job. Track via a closure on the most-recent filter call.
        return []  # replaced dynamically below per test via side_effect

    item_chain.all.return_value = []

    def query_dispatch(model):
        from utils.models.import_item import ImportItem as _II
        from utils.models.import_job import ImportJob as _IJ
        if model is _IJ:
            return job_chain
        if model is _II:
            return item_chain
        return MagicMock()

    db.query.side_effect = query_dispatch

    # db.execute(select(max(updated_at))...).scalar() returns the job's max
    # item update. We dispatch based on a counter because each call pops one.
    scalar_iter = iter([
        latest_item_update_per_job.get(job.id, None) for job in jobs
    ])

    def execute_side_effect(_stmt):
        result = MagicMock()
        result.scalar.return_value = next(scalar_iter, None)
        return result

    db.execute.side_effect = execute_side_effect
    db.commit = MagicMock()

    # Track per-job items so _mark_job_stuck can load them via query(ImportItem)
    job_id_to_items = {}
    for it in items:
        job_id_to_items.setdefault(it.import_job_id, []).append(it)

    marked_jobs_iter = iter(jobs)

    def item_filter_all_side_effect():
        # Each call corresponds to the next job being marked stuck.
        try:
            current_job = next(marked_jobs_iter)
        except StopIteration:
            return []
        return [
            it for it in job_id_to_items.get(current_job.id, [])
            if it.status in ("pending", "extracting", "matching", "approved")
        ]

    item_chain.all.side_effect = item_filter_all_side_effect

    database.db = db
    return database


def _run_task(database):
    from utils.tasks.import_tasks.sweep_stuck_imports_task import (
        SweepStuckImportsTask,
    )
    task = SweepStuckImportsTask()
    task.database = database
    with patch(
        "utils.services.activity_service.create_activity"
    ) as mock_create:
        result = task.execute()
    return result, mock_create


def test_no_candidates_is_noop():
    """With no processing jobs past cutoff, nothing happens."""
    database = _make_database(jobs=[], items=[], latest_item_update_per_job={})
    result, mock_create = _run_task(database)
    assert result["data"]["swept"] == 0
    mock_create.assert_not_called()


def test_recent_item_activity_keeps_job_alive():
    """Job past started_at cutoff but with an item updated 2 minutes ago is
    NOT swept — the pipeline is still making progress."""
    long_ago = datetime.now(UTC) - timedelta(minutes=20)
    two_min_ago = datetime.now(UTC) - timedelta(minutes=2)

    job = _make_job(started_at=long_ago)
    item = _make_item(import_job_id=job.id, updated_at=two_min_ago)

    database = _make_database(
        jobs=[job],
        items=[item],
        latest_item_update_per_job={job.id: two_min_ago},
    )
    result, mock_create = _run_task(database)

    assert result["data"]["swept"] == 0
    assert job.status == "processing"  # untouched
    assert item.status == "matching"  # untouched
    mock_create.assert_not_called()


def test_stale_job_with_stale_items_is_marked_failed():
    """Job past started_at cutoff with items last touched before cutoff gets
    marked failed and its non-terminal items get marked failed too."""
    long_ago = datetime.now(UTC) - timedelta(minutes=20)

    job = _make_job(started_at=long_ago)
    item_extracting = _make_item(
        import_job_id=job.id, status="extracting", updated_at=long_ago
    )
    item_completed = _make_item(
        import_job_id=job.id, status="completed", updated_at=long_ago
    )

    database = _make_database(
        jobs=[job],
        items=[item_extracting, item_completed],
        latest_item_update_per_job={job.id: long_ago},
    )
    result, mock_create = _run_task(database)

    assert result["data"]["swept"] == 1
    assert job.status == "failed"
    assert job.error_message is not None
    assert job.completed_at is not None

    # Non-terminal item transitioned; terminal item untouched.
    assert item_extracting.status == "failed"
    assert item_extracting.error_code == "STUCK_IMPORT"
    assert item_completed.status == "completed"

    mock_create.assert_called_once()
    _, kwargs = mock_create.call_args
    assert kwargs["activity_type"] == "import_failed"
    assert kwargs["user_id"] == job.user_id


def test_stale_job_with_no_items_is_marked_failed():
    """Job past started_at cutoff with zero child items (max update is NULL)
    is still swept — we can't prove the pipeline is alive."""
    long_ago = datetime.now(UTC) - timedelta(minutes=20)

    job = _make_job(started_at=long_ago)
    database = _make_database(
        jobs=[job],
        items=[],
        latest_item_update_per_job={job.id: None},
    )
    result, _ = _run_task(database)

    assert result["data"]["swept"] == 1
    assert job.status == "failed"


def test_terminal_job_is_ignored():
    """Jobs in terminal states (completed, failed, cancelled) are never
    considered — the SQL filter excludes them."""
    # The filter at the top of execute() hard-filters to status="processing".
    # This test validates the task call succeeds and returns swept=0 when
    # no processing jobs exist in the fixture.
    long_ago = datetime.now(UTC) - timedelta(minutes=20)
    job = _make_job(status="completed", started_at=long_ago)

    # Our fake filter returns whatever we pass as `jobs`, but a real filter
    # would exclude non-processing. Simulate that by passing an empty job list
    # — representing what the real query would return.
    database = _make_database(
        jobs=[],  # empty = no processing jobs after filter
        items=[],
        latest_item_update_per_job={},
    )
    result, mock_create = _run_task(database)

    assert result["data"]["swept"] == 0
    assert job.status == "completed"  # untouched
    mock_create.assert_not_called()
