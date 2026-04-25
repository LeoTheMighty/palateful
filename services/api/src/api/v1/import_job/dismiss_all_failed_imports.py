"""Dismiss all failed import items owned by the current user in one call.

Backs the "Clear all failed" button in the import hub.
"""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select, update
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.user import User
from utils.models.user_activity import UserActivity

from .counters import recompute_import_job_counters


class DismissAllFailedImports(AsyncEndpoint):
    """Bulk-dismiss every failed ImportItem owned by the requesting user."""

    async def execute(self):
        user: User = self.user
        now = datetime.now(UTC)

        # Find all failed, not-already-dismissed items under the user's jobs.
        candidate_result = await self.database.db.execute(
            select(ImportItem)
            .join(ImportJob, ImportJob.id == ImportItem.import_job_id)
            .where(
                ImportJob.user_id == user.id,
                ImportItem.status == "failed",
                ImportItem.dismissed_at.is_(None),
            )
        )
        candidate_items = list(candidate_result.scalars().all())

        dismissed_count = 0
        affected_job_ids: set = set()
        affected_item_ids: list[str] = []

        for item in candidate_items:
            item.dismissed_at = now
            dismissed_count += 1
            affected_job_ids.add(item.import_job_id)
            affected_item_ids.append(str(item.id))

        # For each touched job, if ALL its items are now dismissed, mark the
        # job dismissed too. (If find_by somehow returned None for a job_id
        # that we just updated items for, we'd have a deeper data problem —
        # no defensive guard here.)
        for job_id in affected_job_ids:
            job = await self.database.find_by(ImportJob, id=job_id)
            siblings_result = await self.database.db.execute(
                select(ImportItem).where(ImportItem.import_job_id == job_id)
            )
            siblings = list(siblings_result.scalars().all())
            if siblings and all(
                sib.dismissed_at is not None for sib in siblings
            ):
                job.dismissed_at = now
            # Decrement the cached counters so the activity-screen badge
            # drops to 0 immediately.
            await recompute_import_job_counters(self.database.db, job)

        # Mark linked import_failed activities as read for each dismissed
        # item. We do this in a single UPDATE per item to avoid an N+1;
        # Python loop is fine because the list is bounded by the user's
        # failed imports and there typically won't be many.
        for item_id in affected_item_ids:
            stmt = (
                update(UserActivity)
                .where(
                    UserActivity.user_id == user.id,
                    UserActivity.type == "import_failed",
                    UserActivity.metadata_json["import_item_id"].astext
                    == item_id,
                )
                .values(read=True)
                .execution_options(synchronize_session=False)
            )
            await self.database.db.execute(stmt)

        await self.database.db.commit()

        return success(
            data=DismissAllFailedImports.Response(
                dismissed_count=dismissed_count,
            )
        )

    class Response(BaseModel):
        dismissed_count: int
