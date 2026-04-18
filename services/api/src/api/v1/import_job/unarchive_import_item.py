"""Unarchive a single import item.

Clears `archived_at` so the item returns to the default Imports list.
Used by the See-all footer's swipe-right-to-unarchive (ahr-5).
Idempotent: calling it on an already-active row is a 200 no-op.
"""

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class UnarchiveImportItem(Endpoint):
    """Unarchive an ImportItem row."""

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
                detail="You don't have permission to unarchive this import item",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        if item.archived_at is not None:
            item.archived_at = None
            self.db.add(item)
            self.db.commit()

        return success(data=UnarchiveImportItem.Response(id=str(item.id)))

    class Response(BaseModel):
        id: str
