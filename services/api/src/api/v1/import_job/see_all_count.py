"""See-all count endpoint for the Imports tab.

Returns the counts that back the Imports-tab See-all footer label
without fetching rows.

``archived`` — items that have been explicitly archived.
``read_and_old_completed`` — items that reached a *terminal* outcome
(``completed`` or ``skipped``) AND are older than 30 days AND not
archived. ``skipped`` items (e.g. photo imports that couldn't produce a
recipe) are no less historical than ``completed`` ones; excluding them
would hide 20+ rows of real user activity from history.
``total`` — the sum.
"""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.user import User

_OLDER_THAN_DAYS = 30
_TERMINAL_STATUSES = ("completed", "skipped")


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
                ImportItem.status.in_(_TERMINAL_STATUSES),
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
