"""Batch list import items endpoint (ffm-2).

Closes the N+1 pattern the Flutter Activity Hub used to hit: one
``GET /v1/import-jobs/{id}/items`` per visible import job. With the
batch endpoint the same tab renders its rows in a single round-trip.
"""

from datetime import datetime

from api.v1.import_job.list_import_items import (
    _extract_confidence_fields,
    _extract_inferred_fields,
)
from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User

MAX_JOB_IDS = 50


class ListImportItemsBatch(AsyncEndpoint):
    """Return a flat list of import items across multiple jobs.

    Access is checked per-job. Jobs the caller cannot access are
    silently dropped from the response rather than 403-ing the whole
    request — callers typically pass job_ids derived from
    ``GET /v1/import-jobs`` (already access-filtered), and silent-drop
    ensures the batch endpoint can never be used as an enumeration
    oracle against private jobs.

    The default behavior mirrors the per-job endpoint: ``archived_at``
    filter is ON (hides archived rows); ``include_archived=true``
    flips it off for the See-all pagination path.
    """

    async def execute(
        self,
        job_ids: str,
        status: str | None = None,
        include_archived: bool = False,
    ):
        user: User = self.user

        ids = [s.strip() for s in (job_ids or "").split(",") if s.strip()]
        if not ids:
            raise APIException(
                status_code=400,
                detail="job_ids_required",
                code=ErrorCode.VALIDATION_ERROR,
            )
        if len(ids) > MAX_JOB_IDS:
            raise APIException(
                status_code=400,
                detail=f"job_ids_over_cap (max {MAX_JOB_IDS})",
                code=ErrorCode.VALIDATION_ERROR,
            )

        seen: set[str] = set()
        deduped: list[str] = []
        for x in ids:
            if x not in seen:
                seen.add(x)
                deduped.append(x)
        ids = deduped

        jobs_result = await self.database.db.execute(
            select(ImportJob).where(ImportJob.id.in_(ids))
        )
        jobs = list(jobs_result.scalars().all())
        if not jobs:
            return success(
                data=ListImportItemsBatch.Response(items=[]),
            )

        book_ids = list(
            {str(j.recipe_book_id) for j in jobs if j.recipe_book_id}
        )
        accessible_book_ids: set[str] = set()
        if book_ids:
            memberships_result = await self.database.db.execute(
                select(RecipeBookUser).where(
                    RecipeBookUser.user_id == user.id,
                    RecipeBookUser.recipe_book_id.in_(book_ids),
                )
            )
            memberships = list(memberships_result.scalars().all())
            accessible_book_ids = {
                str(m.recipe_book_id) for m in memberships
            }

        accessible_job_ids: list[str] = []
        for j in jobs:
            if str(j.user_id) == str(user.id) or str(j.recipe_book_id) in accessible_book_ids:
                accessible_job_ids.append(str(j.id))

        if not accessible_job_ids:
            return success(
                data=ListImportItemsBatch.Response(items=[]),
            )

        stmt = select(ImportItem).where(
            ImportItem.import_job_id.in_(accessible_job_ids)
        )
        if status:
            stmt = stmt.where(ImportItem.status == status)
        if not include_archived:
            stmt = stmt.where(ImportItem.archived_at.is_(None))

        stmt = stmt.order_by(
            ImportItem.import_job_id,
            ImportItem.created_at.desc(),
            ImportItem.id.desc(),
        )
        items_result = await self.database.db.execute(stmt)
        items = list(items_result.scalars().all())

        item_responses: list[ListImportItemsBatch.BatchItem] = []
        for item in items:
            recipe_name = None
            needs_review = False
            if item.parsed_recipe:
                recipe_name = item.parsed_recipe.get("name")
                ingredients = item.parsed_recipe.get("ingredients", [])
                needs_review = any(
                    ing.get("needs_review", False) for ing in ingredients
                )

            confidence_score, confidence_source = (
                _extract_confidence_fields(item.parsed_recipe)
            )

            item_responses.append(
                ListImportItemsBatch.BatchItem(
                    id=str(item.id),
                    job_id=str(item.import_job_id),
                    status=item.status,
                    source_type=item.source_type,
                    source_url=item.source_url,
                    recipe_name=recipe_name,
                    error_message=item.error_message,
                    needs_review=(
                        needs_review
                        or item.status == "awaiting_review"
                    ),
                    ai_cost_cents=item.ai_cost_cents,
                    created_at=item.created_at,
                    archived_at=item.archived_at,
                    last_successful_stage=item.last_successful_stage,
                    last_retry_at=item.last_retry_at,
                    awaiting_review_reason=item.awaiting_review_reason,
                    confidence_score=confidence_score,
                    confidence_source=confidence_source,
                    inferred_fields=_extract_inferred_fields(
                        item.parsed_recipe
                    ),
                    created_recipe_id=(
                        str(item.created_recipe_id)
                        if item.created_recipe_id
                        else None
                    ),
                )
            )

        return success(
            data=ListImportItemsBatch.Response(items=item_responses),
        )

    class BatchItem(BaseModel):
        id: str
        job_id: str
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
        inferred_fields: list[str] = []
        created_recipe_id: str | None = None

    class Response(BaseModel):
        items: list["ListImportItemsBatch.BatchItem"]
