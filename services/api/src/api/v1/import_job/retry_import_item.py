"""Retry import item endpoint.

Resumes a failed import item from the last stage that completed
successfully, so we don't re-run OCR or extraction that already worked.
"""

from pydantic import BaseModel
from sqlalchemy import func
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.constants import STAGE_EXTRACTED, STAGE_MATCHED, STAGE_PARSED
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.tasks.import_tasks.create_recipe_task import create_recipe_task
from utils.tasks.import_tasks.extract_recipe_task import extract_task
from utils.tasks.import_tasks.match_ingredients_task import match_ingredients_task
from utils.tasks.import_tasks.parse_source_task import parse_source_task


def _dispatch_parse(item: ImportItem, job: ImportJob, user_id: str) -> None:
    parse_source_task.delay(str(job.id))


def _dispatch_extract(item: ImportItem, job: ImportJob, user_id: str) -> None:
    extract_task.delay(item_ids=[str(item.id)], user_id=user_id)


def _dispatch_match(item: ImportItem, job: ImportJob, user_id: str) -> None:
    match_ingredients_task.delay(item_id=str(item.id), user_id=user_id)


def _dispatch_create(item: ImportItem, job: ImportJob, user_id: str) -> None:
    create_recipe_task.delay(item_id=str(item.id), user_id=user_id)


# Stage marker → (task_name, next_item_status, dispatcher)
#
# None and unknown values fall through to the full-restart entry at the end
# (see _lookup_stage below).
_STAGE_PLAN: dict[str | None, tuple[str, str, callable]] = {
    STAGE_PARSED: ("extract_recipe_task", "extracting", _dispatch_extract),
    STAGE_EXTRACTED: ("match_ingredients_task", "matching", _dispatch_match),
    STAGE_MATCHED: ("create_recipe_task", "approved", _dispatch_create),
}

_FULL_RESTART_PLAN: tuple[str, str, callable] = (
    "parse_source_task",
    "pending",
    _dispatch_parse,
)


def _lookup_stage(stage: str | None) -> tuple[str, str, callable]:
    """Return the (task_name, next_status, dispatcher) for the given stage
    marker. NULL and unknown values map to a full restart from the top of
    the pipeline.
    """
    return _STAGE_PLAN.get(stage, _FULL_RESTART_PLAN)


class RetryImportItem(Endpoint):
    """Retry a failed import item from its last successful stage."""

    def execute(self, item_id: str):
        user: User = self.user

        item = self.database.find_by(ImportItem, id=item_id)
        if not item:
            raise APIException(
                status_code=404,
                detail=f"Import item with ID '{item_id}' not found",
                code=ErrorCode.IMPORT_ITEM_NOT_FOUND,
            )

        job = self.database.find_by(ImportJob, id=item.import_job_id)
        if not job:
            raise APIException(
                status_code=404,
                detail="Import job not found",
                code=ErrorCode.IMPORT_JOB_NOT_FOUND,
            )

        # Ownership: must be owner or editor of the book.
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=job.recipe_book_id,
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to retry this import item",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        # Retryable iff the item itself failed OR the parent job was marked
        # failed by the sweeper (in which case child items may still show
        # mid-pipeline statuses).
        if item.status != "failed" and job.status != "failed":
            raise APIException(
                status_code=400,
                detail=(
                    f"Cannot retry item in '{item.status}' status "
                    f"(job status: '{job.status}')"
                ),
                code=ErrorCode.IMPORT_ITEM_INVALID_STATUS,
            )

        resumed_from_stage = item.last_successful_stage or "start"
        task_name, next_status, dispatcher = _lookup_stage(
            item.last_successful_stage
        )

        # Reset error bookkeeping for the retry. Clear the
        # awaiting_review_reason too — it'll be re-populated by the
        # matching/extract tasks if the retry lands back in
        # awaiting_review.
        item.error_message = None
        item.error_code = None
        item.retry_count = (item.retry_count or 0) + 1
        item.last_retry_at = func.now()
        item.awaiting_review_reason = None
        item.status = next_status

        # If the parent job was marked failed (by sweeper or downstream
        # logic), flip it back to processing so the UI reflects the retry.
        # Otherwise leave the job status alone — the item-level retry is
        # sufficient.
        if job.status == "failed":
            job.status = "processing"
            job.error_message = None
            job.completed_at = None

        self.database.db.commit()

        # Dispatch outside the commit so a broker failure doesn't lose the
        # state reset. Concurrent retries are an accepted risk for MVP (see
        # epic-mvp-finalization.md); two tasks racing on the same item can
        # produce duplicate Recipe rows from create_recipe_task.
        dispatcher(item, job, str(user.id))

        return success(
            data=RetryImportItem.Response(
                item_id=str(item.id),
                dispatched_task=task_name,
                resumed_from_stage=resumed_from_stage,
                status=item.status,
            )
        )

    class Response(BaseModel):
        item_id: str
        dispatched_task: str
        resumed_from_stage: str
        status: str
