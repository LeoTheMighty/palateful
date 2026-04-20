"""See-all count endpoint for the Imports tab (afh-2).

Returns the counts that back the Imports-tab See-all footer label
without fetching rows.

``archived`` — items that have been explicitly archived.
``read_and_old_completed`` — items that are ``completed`` AND older
than 30 days AND not archived (they've aged out of the active list but
aren't deleted).
``total`` — the sum.
"""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.user import User

_OLDER_THAN_DAYS = 30


class ImportSeeAllCount(Endpoint):
    """Imports See-all triple (archived, read_and_old_completed, total)."""

    def execute(self):
        user: User = self.user
        cutoff = datetime.now(UTC) - timedelta(days=_OLDER_THAN_DAYS)

        archived = (
            self.db.query(ImportItem)
            .join(ImportJob, ImportItem.import_job_id == ImportJob.id)
            .filter(
                ImportJob.user_id == user.id,
                ImportItem.archived_at.isnot(None),
            )
            .count()
        )

        read_and_old_completed = (
            self.db.query(ImportItem)
            .join(ImportJob, ImportItem.import_job_id == ImportJob.id)
            .filter(
                ImportJob.user_id == user.id,
                ImportItem.archived_at.is_(None),
                ImportItem.status == "completed",
                ImportItem.created_at < cutoff,
            )
            .count()
        )

        return success(
            data=ImportSeeAllCount.Response(
                archived=archived,
                read_and_old_completed=read_and_old_completed,
                total=archived + read_and_old_completed,
            )
        )

    class Response(BaseModel):
        archived: int
        read_and_old_completed: int
        total: int
