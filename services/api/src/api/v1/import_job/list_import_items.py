"""List import items endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


def _extract_confidence_fields(
    parsed_recipe: dict | None,
) -> tuple[float | None, str | None]:
    """Hoist ``confidence_score`` + ``confidence_source`` from parsed_recipe.

    Mirrors the helper in ``get_import_item.py`` — kept local here so the
    list endpoint doesn't depend on the detail endpoint's module. Drops
    out-of-range or malformed values so legacy rows don't leak garbage.
    """
    if not parsed_recipe:
        return (None, None)
    raw_score = parsed_recipe.get("confidence_score")
    raw_source = parsed_recipe.get("confidence_source")

    score: float | None = None
    if isinstance(raw_score, int | float) and not isinstance(raw_score, bool):
        f = float(raw_score)
        if 0.0 <= f <= 1.0:
            score = f

    source: str | None = None
    if isinstance(raw_source, str) and raw_source in ("model", "heuristic"):
        source = raw_source

    return (score, source)


class ListImportItems(Endpoint):
    """List import items for a job."""

    def execute(
        self,
        job_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False,
    ):
        """List import items for a job.

        ``include_archived`` defaults to false so the default feed hides
        archived rows; the See-all footer flips it on.
        """
        user: User = self.user

        job = self.database.find_by(ImportJob, id=job_id)
        if not job:
            raise APIException(
                status_code=404,
                detail=f"Import job with ID '{job_id}' not found",
                code=ErrorCode.IMPORT_JOB_NOT_FOUND,
            )

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

        query = self.database.db.query(ImportItem).filter(
            ImportItem.import_job_id == job_id
        )

        if status:
            query = query.filter(ImportItem.status == status)

        if not include_archived:
            query = query.filter(ImportItem.archived_at.is_(None))

        total = query.count()

        items = (
            query.order_by(ImportItem.created_at).offset(offset).limit(limit).all()
        )

        item_responses = []
        for item in items:
            recipe_name = None
            needs_review = False

            if item.parsed_recipe:
                recipe_name = item.parsed_recipe.get("name")
                ingredients = item.parsed_recipe.get("ingredients", [])
                needs_review = any(ing.get("needs_review", False) for ing in ingredients)

            confidence_score, confidence_source = _extract_confidence_fields(
                item.parsed_recipe
            )

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
                    archived_at=item.archived_at,
                    last_successful_stage=item.last_successful_stage,
                    last_retry_at=item.last_retry_at,
                    awaiting_review_reason=item.awaiting_review_reason,
                    confidence_score=confidence_score,
                    confidence_source=confidence_source,
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
        archived_at: datetime | None = None
        last_successful_stage: str | None = None
        last_retry_at: datetime | None = None
        awaiting_review_reason: str | None = None
        confidence_score: float | None = None
        confidence_source: str | None = None

    class Response(BaseModel):
        items: list["ListImportItems.ItemSummary"]
        total: int
        has_more: bool
