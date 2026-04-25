"""Shared helper that recomputes ImportJob counter fields from live item state.

Endpoints that mutate an ImportItem's status (approve / skip / dismiss) must
call this so the cached counters on the parent ImportJob stay consistent
with reality. Otherwise the UI shows stale badges like "(1) pending review"
after the user already approved the only item — the classic "(1) + All Set"
mismatch.
"""

from sqlalchemy import func, select
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob


async def _count_by_status(db, job_id, status: str) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(ImportItem)
        .where(
            ImportItem.import_job_id == job_id,
            ImportItem.status == status,
            ImportItem.dismissed_at.is_(None),
        )
    )
    return result.scalar_one()


async def recompute_import_job_counters(db, job: ImportJob) -> None:
    """Rebuild ``job.{succeeded,failed,pending_review}_items`` from item rows.

    Dismissed items (``dismissed_at IS NOT NULL``) are excluded so the
    badges on the activity screen don't persist after the user clears a
    failed import.

    Caller is responsible for committing the transaction. Three scalar
    COUNT queries instead of a single GROUP BY because the shape is
    trivial to mock and the cardinality is tiny (< 20 items per job).
    """
    job.succeeded_items = await _count_by_status(db, job.id, "completed")
    job.failed_items = await _count_by_status(db, job.id, "failed")
    job.pending_review_items = await _count_by_status(
        db, job.id, "awaiting_review"
    )
