"""Update import item endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class UpdateImportItem(Endpoint):
    """Update import item with user edits."""

    def execute(self, item_id: str, params: "UpdateImportItem.Params"):
        """
        Update import item with user edits.

        Args:
            item_id: The import item ID.
            params: Update parameters.

        Returns:
            Updated import item data.
        """
        user: User = self.user

        # Load import item
        item = self.database.find_by(ImportItem, id=item_id)
        if not item:
            raise APIException(
                status_code=404,
                detail=f"Import item with ID '{item_id}' not found",
                code=ErrorCode.IMPORT_ITEM_NOT_FOUND,
            )

        # Load job for access check
        job = self.database.find_by(ImportJob, id=item.import_job_id)
        if not job:
            raise APIException(
                status_code=404,
                detail="Import job not found",
                code=ErrorCode.IMPORT_JOB_NOT_FOUND,
            )

        # Check access - must be owner or editor
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=job.recipe_book_id,
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to edit this import item",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        # Validate item status
        if item.status in ("completed", "skipped"):
            raise APIException(
                status_code=400,
                detail=f"Cannot update item in {item.status} status",
                code=ErrorCode.IMPORT_ITEM_INVALID_STATUS,
            )

        # Update user edits
        item.user_edits = params.user_edits
        self.database.db.commit()

        return success(
            data=UpdateImportItem.Response(
                id=str(item.id),
                status=item.status,
                user_edits=item.user_edits,
                updated_at=item.updated_at,
            )
        )

    class Params(BaseModel):
        user_edits: dict

    class Response(BaseModel):
        id: str
        status: str
        user_edits: dict | None
        updated_at: datetime
