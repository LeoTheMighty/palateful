"""Dismiss a single failed import item.

Hard dismiss: sets dismissed_at on the item so list endpoints hide it.
No soft-delete, no trash bin — the only safety net is the snackbar undo
on the frontend, which holds local state only.

rf-2 (additive): the response now also carries the full updated
``ImportItemSummary`` under the ``item`` field so the client can patch
its cached state without a GET round-trip. Old fields
(``item_id``, ``dismissed_at``, ``job_dismissed``) stay at the top level
for pre-rf-2 clients.
"""

from datetime import UTC, datetime

from pydantic import BaseModel
from schemas.import_job import ImportItemSummary
from sqlalchemy import select, update
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.models.user_activity import UserActivity

from .counters import recompute_import_job_counters


class DismissImportItem(AsyncEndpoint):
    """Mark a failed ImportItem as dismissed so the UI hides it."""

    async def execute(self, item_id: str):
        user: User = self.user

        item = await self.database.find_by(ImportItem, id=item_id)
        if not item:
            raise APIException(
                status_code=404,
                detail=f"Import item with ID '{item_id}' not found",
                code=ErrorCode.IMPORT_ITEM_NOT_FOUND,
            )

        job = await self.database.find_by(ImportJob, id=item.import_job_id)
        if not job:
            raise APIException(
                status_code=404,
                detail="Import job not found",
                code=ErrorCode.IMPORT_JOB_NOT_FOUND,
            )

        membership = await self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=job.recipe_book_id,
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to dismiss this import item",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        # Only failed items (or items under a failed job) are dismissible.
        if item.status != "failed" and job.status != "failed":
            raise APIException(
                status_code=400,
                detail=(
                    f"Cannot dismiss item in '{item.status}' status "
                    f"(job status: '{job.status}')"
                ),
                code=ErrorCode.IMPORT_ITEM_INVALID_STATUS,
            )

        now = datetime.now(UTC)
        item.dismissed_at = now

        # If every sibling item under the same job is now dismissed, also
        # mark the job as dismissed so it disappears from batch-level lists.
        siblings_result = await self.database.db.execute(
            select(ImportItem).where(ImportItem.import_job_id == job.id)
        )
        siblings = list(siblings_result.scalars().all())
        if all(sib.dismissed_at is not None for sib in siblings):
            job.dismissed_at = now

        # Recompute the job's cached counters so the activity-screen
        # badge decrements when failed items are dismissed.
        await recompute_import_job_counters(self.database.db, job)

        # Auto-mark any linked import_failed activities as read. Dismissing
        # the import is a stronger action than reading the notification.
        activity_stmt = (
            update(UserActivity)
            .where(
                UserActivity.user_id == user.id,
                UserActivity.type == "import_failed",
                UserActivity.metadata_json["import_item_id"].astext
                == str(item.id),
            )
            .values(read=True)
            .execution_options(synchronize_session=False)
        )
        await self.database.db.execute(activity_stmt)

        await self.database.db.commit()

        return success(
            data=DismissImportItem.Response(
                item_id=str(item.id),
                dismissed_at=now.isoformat(),
                job_dismissed=job.dismissed_at is not None,
                item=_item_summary(item),
            )
        )

    class Response(BaseModel):
        # Legacy fields — retained at top level so pre-rf-2 clients keep
        # working. Do NOT remove without a deprecation cycle.
        item_id: str
        dismissed_at: str
        job_dismissed: bool

        # rf-2: full updated item so the client can patch cached state
        # without a round-trip. Optional for cheap rollback.
        item: ImportItemSummary | None = None


def _item_summary(item: ImportItem) -> ImportItemSummary:
    """Shape an ImportItem row for the dismiss response.

    Mirrors the derivation used by `listImportItems` — `recipe_name` +
    `needs_review` come from `parsed_recipe`, not direct columns. For
    dismissed (failed) items `parsed_recipe` is typically None; both
    fields fall through to their defaults.
    """
    parsed = item.parsed_recipe or {}
    recipe_name = parsed.get("name")
    ingredients = parsed.get("ingredients") or []
    flagged = any((ing or {}).get("needs_review", False) for ing in ingredients)
    return ImportItemSummary(
        id=str(item.id),
        status=item.status,
        source_type=item.source_type,
        source_url=item.source_url,
        recipe_name=recipe_name,
        error_message=item.error_message,
        needs_review=bool(flagged or item.status == "awaiting_review"),
        ai_cost_cents=int(item.ai_cost_cents or 0),
        created_at=item.created_at,
    )
