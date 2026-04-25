"""Get import item endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


def _extract_confidence_fields(
    parsed_recipe: dict | None,
) -> tuple[float | None, str | None]:
    """Pull `confidence_score` + `confidence_source` out of parsed_recipe.

    Returns ``(None, None)`` when extraction has not yet run or the
    extractor didn't write either key. Values are validated lightly —
    out-of-range floats are dropped to None so the API response doesn't
    pass through malformed scores from legacy rows.
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


def _extract_inferred_fields(parsed_recipe: dict | None) -> list[str]:
    """efi-4 — hoist ``inferred_fields`` from parsed_recipe to the response root.

    Always returns a list. Legacy rows (no key, or null) return ``[]``.
    Filters to the server-side allow-list so a malformed legacy row
    can't smuggle a bogus name onto the API surface.
    """
    from utils.services.recipe_extractors.inference_prompt import INFERABLE_FIELDS

    if not parsed_recipe:
        return []
    raw = parsed_recipe.get("inferred_fields")
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    clean: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        if item in INFERABLE_FIELDS and item not in seen:
            seen.add(item)
            clean.append(item)
    return clean


_PARSED_RECIPE_KEY = "parsed_recipe"


class GetImportItem(AsyncEndpoint):
    """Get import item details."""

    async def execute(self, item_id: str, include: str | None = None):
        """
        Get import item details.

        Args:
            item_id: The import item ID.
            include: ffm-10 — optional CSV of opt-in fields. The only
                supported value today is ``parsed_recipe``. When
                omitted, the heavy ``parsed_recipe`` blob is ABSENT
                from the response (not null) — activity feed and
                dashboard callers get the lean shape by default.
                The telemetry viewer explicitly sends
                ``?include=parsed_recipe``. Unknown tokens are
                silently dropped for forward-compat.

        Returns:
            Import item data.
        """
        user: User = self.user

        # Load import item
        item = await self.database.find_by(ImportItem, id=item_id)
        if not item:
            raise APIException(
                status_code=404,
                detail=f"Import item with ID '{item_id}' not found",
                code=ErrorCode.IMPORT_ITEM_NOT_FOUND,
            )

        # Load job for access check
        job = await self.database.find_by(ImportJob, id=item.import_job_id)
        if not job:
            raise APIException(
                status_code=404,
                detail="Import job not found",
                code=ErrorCode.IMPORT_JOB_NOT_FOUND,
            )

        # Check access
        membership = await self.database.find_by(
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

        # irrd-3 — convenience hoist so the caret expansion doesn't have
        # to drill into nested parsed_recipe JSON. Null when extraction
        # hasn't run yet.
        confidence_score, confidence_source = _extract_confidence_fields(
            item.parsed_recipe
        )

        response_model = GetImportItem.Response(
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
            last_successful_stage=item.last_successful_stage,
            last_retry_at=item.last_retry_at,
            awaiting_review_reason=item.awaiting_review_reason,
            confidence_score=confidence_score,
            confidence_source=confidence_source,
            inferred_fields=_extract_inferred_fields(item.parsed_recipe),
        )

        # ffm-10: the ``parsed_recipe`` blob is expensive to serialize
        # + ship (can be multi-KB). Drop it from the default response;
        # the telemetry viewer opts in via ``?include=parsed_recipe``.
        requested_parsed = False
        if include is not None:
            tokens = {s.strip() for s in include.split(",") if s.strip()}
            requested_parsed = _PARSED_RECIPE_KEY in tokens

        if requested_parsed:
            return success(data=response_model)

        payload = response_model.model_dump()
        payload.pop(_PARSED_RECIPE_KEY, None)
        return success(data=payload)

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
        confidence_score: float | None = None
        confidence_source: str | None = None
        inferred_fields: list[str] = []
