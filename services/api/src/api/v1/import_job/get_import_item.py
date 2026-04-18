"""Get import item endpoint."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.ingredient import Ingredient
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


def _annotate_pending_review_ingredients(
    parsed_recipe: dict | None,
    session,
) -> dict | None:
    """Add `pending_review_ingredient: true` to ingredients that point at a
    pending-review canonical, or that haven't been matched yet.

    Returns a NEW dict (does not mutate the input) so the persisted
    `parsed_recipe` JSONB stays untouched. Batches the canonical-row
    lookup into a single `WHERE id IN (…)` query — no N+1.
    """
    if not parsed_recipe:
        return parsed_recipe
    ingredients = parsed_recipe.get("ingredients")
    if not ingredients:
        return parsed_recipe

    matched_ids = [
        UUID(str(ing["matched_ingredient_id"]))
        for ing in ingredients
        if ing.get("matched_ingredient_id") is not None
    ]

    pending_set: set[UUID] = set()
    if matched_ids:
        rows = session.execute(
            select(Ingredient.id).where(
                Ingredient.id.in_(matched_ids),
                Ingredient.pending_review.is_(True),
            )
        ).scalars().all()
        pending_set = set(rows)

    annotated_ingredients = []
    for ing in ingredients:
        new_ing = dict(ing)
        raw_id = ing.get("matched_ingredient_id")
        is_pending = (
            raw_id is None or UUID(str(raw_id)) in pending_set
        )
        if is_pending:
            new_ing["pending_review_ingredient"] = True
        annotated_ingredients.append(new_ing)

    annotated = dict(parsed_recipe)
    annotated["ingredients"] = annotated_ingredients
    return annotated


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

        # riip-4: annotate ingredients in parsed_recipe with
        # pending_review_ingredient so the Flutter ✨ badge knows when a
        # canonical was auto-created. Batched query — no N+1.
        annotated_parsed_recipe = _annotate_pending_review_ingredients(
            item.parsed_recipe, self.database.db
        )

        return success(
            data=GetImportItem.Response(
                id=str(item.id),
                status=item.status,
                source_type=item.source_type,
                source_reference=item.source_reference,
                source_url=item.source_url,
                raw_data=item.raw_data or {},
                parsed_recipe=annotated_parsed_recipe,
                user_edits=item.user_edits,
                error_message=item.error_message,
                error_code=item.error_code,
                retry_count=item.retry_count,
                ai_cost_cents=item.ai_cost_cents,
                import_job_id=str(item.import_job_id),
                created_recipe_id=str(item.created_recipe_id) if item.created_recipe_id else None,
                created_at=item.created_at,
                updated_at=item.updated_at,
                last_successful_stage=item.last_successful_stage,
                last_retry_at=item.last_retry_at,
                awaiting_review_reason=item.awaiting_review_reason,
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
        last_successful_stage: str | None = None
        last_retry_at: datetime | None = None
        awaiting_review_reason: str | None = None
