"""List See-all import items endpoint.

Direct item-level query backing the Imports-tab See-all footer. Matches
the predicate used by ``ImportSeeAllCount`` so the count and the list
never disagree:

- ``import_items.archived_at IS NOT NULL``, OR
- ``import_items.archived_at IS NULL AND status IN ('completed','skipped')
  AND created_at < now() - 30d``.

Scoped to the current user via ``import_jobs.user_id`` (join). Items
whose parent job the user cannot access are not returned — the join on
``user_id`` is sufficient because only owner-scoped jobs are listed
here; book-shared access for See-all is explicitly out of scope (the
See-all footer surfaces the caller's own archive history).
"""

from datetime import UTC, datetime, timedelta

from api.v1.import_job.list_import_items import (
    _extract_confidence_fields,
    _extract_inferred_fields,
)
from pagination import (
    InvalidCursorError,
    datetime_to_ms,
    decode_cursor,
    encode_cursor,
)
from pydantic import BaseModel
from sqlalchemy import or_, select, text, tuple_
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.user import User

_MAX_LIMIT = 100
_OLDER_THAN_DAYS = 30
_TERMINAL_STATUSES = ("completed", "skipped")
_NEG_INF = text("'-infinity'::timestamptz")


class ListSeeAllImportItems(AsyncEndpoint):
    """Paginated list of items eligible for the Imports See-all footer."""

    async def execute(self, limit: int = 50, cursor: str | None = None):
        user: User = self.user
        limit = max(1, min(limit, _MAX_LIMIT))
        cutoff = datetime.now(UTC) - timedelta(days=_OLDER_THAN_DAYS)

        stmt = (
            select(ImportItem, ImportJob.source_type)
            .join(ImportJob, ImportItem.import_job_id == ImportJob.id)
            .where(
                ImportJob.user_id == user.id,
                or_(
                    ImportItem.archived_at.isnot(None),
                    (
                        ImportItem.archived_at.is_(None)
                        & ImportItem.status.in_(_TERMINAL_STATUSES)
                        & (ImportItem.created_at < cutoff)
                    ),
                ),
            )
        )

        if cursor is not None:
            try:
                cur_arch_ms, cur_created_ms, cur_id = decode_cursor(cursor)
            except InvalidCursorError as exc:
                raise APIException(
                    status_code=400,
                    detail="invalid_cursor",
                    code=ErrorCode.VALIDATION_ERROR,
                ) from exc
            cur_created = datetime.fromtimestamp(cur_created_ms / 1000, tz=UTC)
            cur_arch_ts = (
                _NEG_INF
                if cur_arch_ms is None
                else datetime.fromtimestamp(cur_arch_ms / 1000, tz=UTC)
            )
            stmt = stmt.where(
                tuple_(
                    text(
                        "COALESCE(import_items.archived_at, "
                        "'-infinity'::timestamptz)"
                    ),
                    ImportItem.created_at,
                    ImportItem.id,
                )
                < tuple_(cur_arch_ts, cur_created, cur_id)
            )

        stmt = stmt.order_by(
            text(
                "COALESCE(import_items.archived_at, "
                "'-infinity'::timestamptz) DESC"
            ),
            ImportItem.created_at.desc(),
            ImportItem.id.desc(),
        ).limit(limit + 1)

        rows_result = await self.database.db.execute(stmt)
        rows = list(rows_result.all())
        has_more = len(rows) > limit
        rows = rows[:limit]

        responses: list[ListSeeAllImportItems.BatchItem] = []
        for item, job_source_type in rows:
            recipe_name = None
            needs_review = False
            if item.parsed_recipe:
                recipe_name = item.parsed_recipe.get("name")
                ingredients = item.parsed_recipe.get("ingredients", [])
                needs_review = any(
                    ing.get("needs_review", False) for ing in ingredients
                )

            confidence_score, confidence_source = _extract_confidence_fields(
                item.parsed_recipe
            )

            responses.append(
                ListSeeAllImportItems.BatchItem(
                    id=str(item.id),
                    job_id=str(item.import_job_id),
                    status=item.status,
                    source_type=item.source_type or job_source_type,
                    source_url=item.source_url,
                    recipe_name=recipe_name,
                    error_message=item.error_message,
                    needs_review=(
                        needs_review or item.status == "awaiting_review"
                    ),
                    ai_cost_cents=item.ai_cost_cents,
                    created_at=item.created_at,
                    archived_at=item.archived_at,
                    last_successful_stage=item.last_successful_stage,
                    last_retry_at=item.last_retry_at,
                    awaiting_review_reason=item.awaiting_review_reason,
                    confidence_score=confidence_score,
                    confidence_source=confidence_source,
                    inferred_fields=_extract_inferred_fields(item.parsed_recipe),
                    created_recipe_id=(
                        str(item.created_recipe_id)
                        if item.created_recipe_id
                        else None
                    ),
                )
            )

        next_cursor: str | None = None
        if has_more and responses:
            last = rows[-1][0]
            next_cursor = encode_cursor(
                datetime_to_ms(last.archived_at),
                datetime_to_ms(last.created_at),
                str(last.id),
            )

        return success(
            data=ListSeeAllImportItems.Response(
                items=responses,
                next_cursor=next_cursor,
            )
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
        items: list["ListSeeAllImportItems.BatchItem"]
        next_cursor: str | None = None
