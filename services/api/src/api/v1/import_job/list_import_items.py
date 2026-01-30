"""List import items endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ListImportItems(Endpoint):
    """List import items for a job."""

    def execute(self, job_id: str, status: str | None = None, limit: int = 50, offset: int = 0):
        """
        List import items for a job.

        Args:
            job_id: The import job ID.
            status: Optional status filter.
            limit: Maximum items to return.
            offset: Offset for pagination.

        Returns:
            List of import items.
        """
        user: User = self.user

        # Load import job
        job = self.database.find_by(ImportJob, id=job_id)
        if not job:
            raise APIException(
                status_code=404,
                detail=f"Import job with ID '{job_id}' not found",
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
                detail="You don't have access to this import job",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        # Build query
        query = self.database.db.query(ImportItem).filter(
            ImportItem.import_job_id == job_id
        )

        if status:
            query = query.filter(ImportItem.status == status)

        # Get total count
        total = query.count()

        # Apply pagination
        items = query.order_by(ImportItem.created_at).offset(offset).limit(limit).all()

        # Build response
        item_responses = []
        for item in items:
            recipe_name = None
            needs_review = False

            if item.parsed_recipe:
                recipe_name = item.parsed_recipe.get("name")
                # Check if any ingredient needs review
                ingredients = item.parsed_recipe.get("ingredients", [])
                needs_review = any(ing.get("needs_review", False) for ing in ingredients)

            item_responses.append(
                ListImportItems.ItemSummary(
                    id=str(item.id),
                    status=item.status,
                    source_type=item.source_type,
                    source_url=item.source_url,
                    recipe_name=recipe_name,
                    error_message=item.error_message,
                    needs_review=needs_review or item.status == "awaiting_review",
                    ai_cost_cents=item.ai_cost_cents,
                    created_at=item.created_at,
                )
            )

        return success(
            data=ListImportItems.Response(
                items=item_responses,
                total=total,
                has_more=offset + len(items) < total,
            )
        )

    class ItemSummary(BaseModel):
        id: str
        status: str
        source_type: str
        source_url: str | None = None
        recipe_name: str | None = None
        error_message: str | None = None
        needs_review: bool = False
        ai_cost_cents: int = 0
        created_at: datetime

    class Response(BaseModel):
        items: list["ListImportItems.ItemSummary"]
        total: int
        has_more: bool
