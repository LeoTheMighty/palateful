"""Archive a single import item.

Sets `archived_at = NOW()` so the item is hidden from the default Imports
list and moves to the See-all footer. In-progress items (pending /
extracting / matching / processing / awaiting_parser) cannot be archived
— the swipe-to-archive affordance is absent on the frontend for blue
rows, but we also enforce it at the API so a racing webhook can't sneak
an in-progress row into an archived state.

The in-progress guard uses `SELECT ... FOR UPDATE` to close the race
where a row's status flips between the initial read and the write: we
re-read `status` under the row lock before deciding. Two concurrent
archive calls on an awaiting-review item end with one 200 success + one
200 no-op (idempotency wins, per Principle 6 of the epic).
"""

from datetime import UTC, datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User

# Statuses for which archive is not allowed. Keep in sync with the
# frontend's "Blue (In Progress)" section mapping in ahr-4 AC13.
_IN_PROGRESS_STATUSES = frozenset(
    {"pending", "extracting", "matching", "processing", "awaiting_parser"}
)


class ArchiveImportItem(Endpoint):
    """Archive an ImportItem row."""

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
                detail="You don't have permission to archive this import item",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        # Re-read status under a row lock to close the webhook race:
        # a row can flip from awaiting_review → processing between the
        # initial find_by() above and the write below. Lock + re-read
        # guarantees we decide on the post-flip status.
        locked = (
            self.db.query(ImportItem)
            .filter(ImportItem.id == item.id)
            .with_for_update()
            .first()
        )
        if locked is None:
            # Concurrent delete is the only way this can happen; treat
            # same as 404.
            raise APIException(
                status_code=404,
                detail=f"Import item with ID '{item_id}' not found",
                code=ErrorCode.IMPORT_ITEM_NOT_FOUND,
            )

        if locked.status in _IN_PROGRESS_STATUSES:
            raise APIException(
                status_code=409,
                detail="cannot archive in-progress import",
                code=ErrorCode.IMPORT_ITEM_INVALID_STATUS,
            )

        if locked.archived_at is None:
            locked.archived_at = datetime.now(UTC)
            self.db.add(locked)
            self.db.commit()

        return success(
            data=ArchiveImportItem.Response(
                id=str(locked.id),
                archived_at=locked.archived_at.isoformat(),
            )
        )

    class Response(BaseModel):
        id: str
        archived_at: str
