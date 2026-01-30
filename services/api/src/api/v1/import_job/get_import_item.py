"""Get import item endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class GetImportItem(Endpoint):
    """Get import item details."""

    def execute(self, item_id: str):
        """
        Get import item details.

        Args:
            item_id: The import item ID.

        Returns:
            Import item data.
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

        # Check access
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=job.recipe_book_id,
        )
        if not membership and job.user_id != user.id:
            raise APIException(
                status_code=403,
                detail="You don't have access to this import item",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        return success(
            data=GetImportItem.Response(
                id=str(item.id),
                status=item.status,
                source_type=item.source_type,
                source_reference=item.source_reference,
                source_url=item.source_url,
                raw_data=item.raw_data or {},
                parsed_recipe=item.parsed_recipe,
                user_edits=item.user_edits,
                error_message=item.error_message,
                error_code=item.error_code,
                retry_count=item.retry_count,
                ai_cost_cents=item.ai_cost_cents,
                import_job_id=str(item.import_job_id),
                created_recipe_id=str(item.created_recipe_id) if item.created_recipe_id else None,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )

    class Response(BaseModel):
        id: str
        status: str
        source_type: str
        source_reference: str | None = None
        source_url: str | None = None
        raw_data: dict
        parsed_recipe: dict | None = None
        user_edits: dict | None = None
        error_message: str | None = None
        error_code: str | None = None
        retry_count: int
        ai_cost_cents: int
        import_job_id: str
        created_recipe_id: str | None = None
        created_at: datetime
        updated_at: datetime
