"""Approve import item endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.tasks.import_tasks.create_recipe_task import create_recipe_task


class ApproveImportItem(Endpoint):
    """Approve import item and create recipe."""

    def execute(self, item_id: str):
        """
        Approve import item and trigger recipe creation.

        Args:
            item_id: The import item ID.

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
                detail="You don't have permission to approve this import item",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        # Validate item status
        if item.status not in ("awaiting_review", "matching"):
            raise APIException(
                status_code=400,
                detail=f"Cannot approve item in {item.status} status",
                code=ErrorCode.IMPORT_ITEM_INVALID_STATUS,
            )

        # Check that we have recipe data
        if not item.parsed_recipe and not item.user_edits:
            raise APIException(
                status_code=400,
                detail="No recipe data to approve",
                code=ErrorCode.IMPORT_NO_RECIPE_DATA,
            )

        # Update status to approved
        item.status = "approved"
        self.database.db.commit()

        # Dispatch recipe creation task
        create_recipe_task.delay(
            item_id=str(item.id),
            user_id=str(user.id),
        )

        return success(
            data=ApproveImportItem.Response(
                id=str(item.id),
                status=item.status,
                message="Recipe creation started",
                updated_at=item.updated_at,
            )
        )

    class Response(BaseModel):
        id: str
        status: str
        message: str
        updated_at: datetime
