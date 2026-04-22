"""Tests for the IMPORT_FAILED transition hooks in extract/create tasks.

The upstream tasks own the status transition; we just assert the
notify hook fires on the `_ -> "failed"` edge exactly once, and NOT
on cancelled jobs or on re-counts of already-failed jobs.
"""

import uuid
from unittest.mock import MagicMock, patch


def _make_job(
    *,
    status="processing",
    total_items=3,
    source_type="url_list",
    source_url=None,
):
    job = MagicMock()
    job.id = uuid.uuid4()
    job.user_id = uuid.uuid4()
    job.status = status
    job.total_items = total_items
    job.succeeded_items = 0
    job.failed_items = 0
    job.pending_review_items = 0
    job.processed_items = 0
    job.source_type = source_type
    job.source_url = source_url
    job.source_filename = None
    job.completed_at = None
    return job


def _wire_extract_task(job, status_counts):
    """Build an ExtractRecipeTask with stubbed DB layer."""
    from utils.tasks.import_tasks.extract_recipe_task import ExtractRecipeTask

    task = ExtractRecipeTask()
    database = MagicMock()
    db = MagicMock()
    database.db = db
    database.find_by.return_value = job
    task.database = database

    # db.query(ImportItem.status, func.count).filter().group_by().all() → counts tuples.
    chained = MagicMock()
    chained.filter.return_value = chained
    chained.group_by.return_value = chained
    chained.all.return_value = list(status_counts.items())
    db.query.return_value = chained
    return task


def _wire_create_task(job, status_counts):
    """Build a CreateRecipeTask with stubbed DB layer."""
    from utils.tasks.import_tasks.create_recipe_task import CreateRecipeTask

    task = CreateRecipeTask()
    database = MagicMock()
    db = MagicMock()
    database.db = db
    task.database = database

    chained = MagicMock()
    chained.filter.return_value = chained
    chained.group_by.return_value = chained
    chained.all.return_value = list(status_counts.items())
    db.query.return_value = chained
    return task


# ---------------------------------------------------------------------------
# extract_recipe_task — transitions into "failed"
# ---------------------------------------------------------------------------

class TestExtractTaskFailedTransition:

    def test_fires_on_all_items_failed_transition(self):
        job = _make_job(status="processing", total_items=3)
        task = _wire_extract_task(job, {"failed": 3})

        with patch(
            "utils.services.import_notifications.notify_import_failed"
        ) as mock_notify:
            task._update_job_counts(job.id)

        assert job.status == "failed"
        mock_notify.assert_called_once()

    def test_no_fire_when_status_was_already_failed(self):
        # Idempotency: a second `_update_job_counts` call after a prior
        # failed transition must not re-fire.
        job = _make_job(status="failed", total_items=3)
        task = _wire_extract_task(job, {"failed": 3})

        with patch(
            "utils.services.import_notifications.notify_import_failed"
        ) as mock_notify:
            task._update_job_counts(job.id)

        mock_notify.assert_not_called()

    def test_cancelled_job_does_not_fire(self):
        # Same guard as create-task's: a cancelled job whose items are
        # all terminal-failed must not flip into `"failed"` and push.
        job = _make_job(status="cancelled", total_items=3)
        task = _wire_extract_task(job, {"failed": 3})

        with patch(
            "utils.services.import_notifications.notify_import_failed"
        ) as mock_notify:
            task._update_job_counts(job.id)

        assert job.status == "cancelled"
        mock_notify.assert_not_called()

    def test_awaiting_review_branch_doesnt_fire_import_failed(self):
        # 2 failed + 1 awaiting_review → job.status stays "awaiting_review",
        # IMPORT_FAILED does NOT fire.
        job = _make_job(status="processing", total_items=3)
        task = _wire_extract_task(
            job, {"failed": 2, "awaiting_review": 1}
        )

        with (
            patch(
                "utils.services.import_notifications.notify_import_failed"
            ) as mock_failed,
            patch(
                "utils.services.import_notifications.notify_import_needs_review"
            ) as mock_review,
        ):
            task._update_job_counts(job.id)

        assert job.status == "awaiting_review"
        mock_failed.assert_not_called()
        mock_review.assert_called_once()


# ---------------------------------------------------------------------------
# create_recipe_task — transitions into "failed" post-approval
# ---------------------------------------------------------------------------

class TestCreateTaskFailedTransition:

    def test_fires_on_all_approved_items_failing_create(self):
        job = _make_job(status="awaiting_review", total_items=2)
        task = _wire_create_task(job, {"failed": 2})

        with patch(
            "utils.services.import_notifications.notify_import_failed"
        ) as mock_notify:
            task._update_job_counts(job)

        assert job.status == "failed"
        assert job.completed_at is not None
        mock_notify.assert_called_once()

    def test_partial_failure_still_completes_without_firing(self):
        # 1 completed + 1 failed → job.status becomes "completed"
        # (epic's create_recipe_task matching loop). No IMPORT_FAILED.
        job = _make_job(status="awaiting_review", total_items=2)
        task = _wire_create_task(job, {"completed": 1, "failed": 1})

        with patch(
            "utils.services.import_notifications.notify_import_failed"
        ) as mock_notify:
            task._update_job_counts(job)

        assert job.status == "completed"
        mock_notify.assert_not_called()

    def test_cancelled_job_does_not_fire(self):
        # A cancelled job with all items terminal-failed must NOT flip
        # to `"failed"` and fire IMPORT_FAILED on recount. Guard added
        # in the task short-circuits when previous_status == "cancelled".
        job = _make_job(status="cancelled", total_items=3)
        task = _wire_create_task(job, {"failed": 3})

        with patch(
            "utils.services.import_notifications.notify_import_failed"
        ) as mock_notify:
            task._update_job_counts(job)

        assert job.status == "cancelled"
        mock_notify.assert_not_called()
