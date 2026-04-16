"""Dismiss a single failed import item.

Hard dismiss: sets dismissed_at on the item so list endpoints hide it.
No soft-delete, no trash bin — the only safety net is the snackbar undo
on the frontend, which holds local state only.
"""

from datetime import UTC, datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.models.user_activity import UserActivity

from .counters import recompute_import_job_counters


class DismissImportItem(Endpoint):
    """Mark a failed ImportItem as dismissed so the UI hides it."""

    def execute(self, item_id: str):
        user: User = self.user

        item = self.database.find_by(ImportItem, id=item_id)
        if not item:
            raise APIException(
                status_code=404,
                detail=f"Import item with ID '{item_id}' not found",
                code=ErrorCode.IMPORT_ITEM_NOT_FOUND,
            )

        job = self.database.find_by(ImportJob, id=item.import_job_id)
        if not job:
            raise APIException(
                status_code=404,
                detail="Import job not found",
                code=ErrorCode.IMPORT_JOB_NOT_FOUND,
            )

        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=job.recipe_book_id,
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to dismiss this import item",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        # Only failed items (or items under a failed job) are dismissible.
        if item.status != "failed" and job.status != "failed":
            raise APIException(
                status_code=400,
                detail=(
                    f"Cannot dismiss item in '{item.status}' status "
                    f"(job status: '{job.status}')"
                ),
                code=ErrorCode.IMPORT_ITEM_INVALID_STATUS,
            )

        now = datetime.now(UTC)
        item.dismissed_at = now

        # If every sibling item under the same job is now dismissed, also
        # mark the job as dismissed so it disappears from batch-level lists.
        siblings = (
            self.database.db.query(ImportItem)
            .filter(ImportItem.import_job_id == job.id)
            .all()
        )
        if all(sib.dismissed_at is not None for sib in siblings):
            job.dismissed_at = now

        # Recompute the job's cached counters so the activity-screen
        # badge decrements when failed items are dismissed.
        recompute_import_job_counters(self.database.db, job)

        # Auto-mark any linked import_failed activities as read. Dismissing
        # the import is a stronger action than reading the notification.
        self.database.db.query(UserActivity).filter(
            UserActivity.user_id == user.id,
            UserActivity.type == "import_failed",
            UserActivity.metadata_json["import_item_id"].astext == str(item.id),
        ).update(
            {UserActivity.read: True},
            synchronize_session=False,
        )

        self.database.db.commit()

        return success(
            data=DismissImportItem.Response(
                item_id=str(item.id),
                dismissed_at=now.isoformat(),
                job_dismissed=job.dismissed_at is not None,
            )
        )

    class Response(BaseModel):
        item_id: str
        dismissed_at: str
        job_dismissed: bool
