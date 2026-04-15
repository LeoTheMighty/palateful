"""Sweep stuck imports task - marks ImportJob rows as failed when their
pipeline has silently stalled.

An ImportJob is considered "stuck" when it has been in `processing` status
for longer than STUCK_IMPORT_JOB_TIMEOUT_MINUTES AND none of its child
ImportItem rows have been updated for that same window. This catches hard
crashes (worker OOM, pod killed, unhandled exceptions before the except
block runs) that leave jobs in a ghost "processing" state forever.

Runs periodically via Celery Beat.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from utils.api.endpoint import success
from utils.constants import STUCK_IMPORT_JOB_TIMEOUT_MINUTES
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.services.celery import celery_app
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

# Don't touch more than this many stuck jobs per sweep — the next sweep
# will pick up any overflow.
MAX_JOBS_PER_SWEEP = 100

NON_TERMINAL_ITEM_STATUSES = (
    "pending",
    "extracting",
    "matching",
    "approved",
)


class SweepStuckImportsTask(BaseTask):
    """Mark stalled ImportJob rows as failed."""

    name = "sweep_stuck_imports_task"

    def execute(self):
        cutoff = datetime.now(UTC) - timedelta(
            minutes=STUCK_IMPORT_JOB_TIMEOUT_MINUTES
        )

        # Candidates: processing jobs that started before the cutoff.
        candidate_jobs = (
            self.database.db.query(ImportJob)
            .filter(
                ImportJob.status == "processing",
                ImportJob.started_at.isnot(None),
                ImportJob.started_at < cutoff,
            )
            .limit(MAX_JOBS_PER_SWEEP)
            .all()
        )

        if not candidate_jobs:
            return success({"swept": 0})

        swept = 0
        for job in candidate_jobs:
            # Second gate: no child item has been touched since the cutoff.
            # If any item is newer than cutoff, the pipeline is still making
            # progress (just slowly) and we leave it alone.
            latest_item_update = self.database.db.execute(
                select(func.max(ImportItem.updated_at)).where(
                    ImportItem.import_job_id == job.id
                )
            ).scalar()

            if latest_item_update is not None and latest_item_update >= cutoff:
                continue

            self._mark_job_stuck(job)
            swept += 1

        if swept > 0:
            self.database.db.commit()
            logger.info("Swept %d stuck import jobs", swept)

        return success({"swept": swept})

    def _mark_job_stuck(self, job: ImportJob) -> None:
        """Flip a stuck job (and its non-terminal items) to failed and drop an
        activity row so the user sees it in the hub.
        """
        now = datetime.now(UTC)
        reason = "Import stalled — no progress for 10 minutes"

        job.status = "failed"
        job.error_message = reason
        job.completed_at = now

        # Mark any non-terminal child items as failed so the UI surfaces them.
        non_terminal_items = (
            self.database.db.query(ImportItem)
            .filter(
                ImportItem.import_job_id == job.id,
                ImportItem.status.in_(NON_TERMINAL_ITEM_STATUSES),
            )
            .all()
        )
        for item in non_terminal_items:
            item.status = "failed"
            item.error_message = "Stage stalled"
            item.error_code = "STUCK_IMPORT"

        try:
            from utils.services.activity_service import create_activity

            create_activity(
                self.database.db,
                user_id=job.user_id,
                activity_type="import_failed",
                title="Your import got stuck",
                subtitle="Tap to retry.",
                metadata={"import_job_id": str(job.id)},
                action_url=f"/recipes/import/review-list/{job.id}",
            )
        except Exception:
            # Activity creation is best-effort; a failure here must not roll
            # back the job status update.
            logger.warning(
                "Failed to create stuck-import activity for job %s",
                job.id,
                exc_info=True,
            )

        logger.info(
            "Marked job %s stuck (started_at=%s, items_touched=%d)",
            job.id,
            job.started_at,
            len(non_terminal_items),
        )


# Register task with Celery
sweep_stuck_imports_task = celery_app.register_task(SweepStuckImportsTask())
