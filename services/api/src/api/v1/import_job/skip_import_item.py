"""Skip import item endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class SkipImportItem(Endpoint):
    """Skip import item."""

    def execute(self, item_id: str):
        """
        Skip import item (don't import this recipe).

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
                detail="You don't have permission to skip this import item",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        # Validate item status
        if item.status in ("completed", "skipped"):
            raise APIException(
                status_code=400,
                detail=f"Cannot skip item in {item.status} status",
                code=ErrorCode.IMPORT_ITEM_INVALID_STATUS,
            )

        # Update status to skipped
        item.status = "skipped"
        self.database.db.commit()

        # Update job counts
        self._update_job_counts(job)

        return success(
            data=SkipImportItem.Response(
                id=str(item.id),
                status=item.status,
                updated_at=item.updated_at,
            )
        )

    def _update_job_counts(self, job: ImportJob):
        """Update import job counts."""
        counts = self.database.db.query(
            ImportItem.status,
            func.count(ImportItem.id)
        ).filter(
            ImportItem.import_job_id == job.id
        ).group_by(ImportItem.status).all()

        status_counts = dict(counts)

        job.succeeded_items = status_counts.get("completed", 0)
        job.failed_items = status_counts.get("failed", 0)
        job.pending_review_items = status_counts.get("awaiting_review", 0)

        # Check if job is complete
        total_final = (
            job.succeeded_items +
            job.failed_items +
            status_counts.get("skipped", 0)
        )
        if total_final >= job.total_items:
            job.status = "completed"
        elif job.pending_review_items > 0:
            job.status = "awaiting_review"

        self.database.db.commit()

    class Response(BaseModel):
        id: str
        status: str
        updated_at: datetime
