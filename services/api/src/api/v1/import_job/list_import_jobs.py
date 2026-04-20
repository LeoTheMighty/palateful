"""List import jobs endpoint."""

from datetime import UTC, datetime

from pagination import (
    InvalidCursorError,
    datetime_to_ms,
    decode_cursor,
    encode_cursor,
)
from pydantic import BaseModel
from sqlalchemy import text, tuple_
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_job import ImportJob
from utils.models.user import User

_MAX_LIMIT = 100
_NEG_INF = text("'-infinity'::timestamptz")


class ListImportJobs(Endpoint):
    """List all import jobs for the current user."""

    def execute(
        self,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
        include_archived: bool = False,
        archived_only: bool = False,
        cursor: str | None = None,
    ):
        """List import jobs for the authenticated user.

        ``include_archived`` / ``archived_only`` back the Imports-tab
        See-all footer (ahr-5). Default list (both false) keeps the
        existing behavior of hiding archived rows alongside dismissed
        rows. ``archived_only=true`` returns only archived rows and
        implies ``include_archived=true`` — the combination
        ``archived_only=true & include_archived=false`` is a contradiction
        that returns 400.

        ``cursor`` (afh-1b) enables the See-all footer's unbounded-depth
        scroll. Mutually exclusive with ``offset``. In See-all mode
        (``include_archived=True`` or ``archived_only=True``) the cursor
        + ORDER BY use the 3-key row-value compare.
        """
        user: User = self.user

        if archived_only and not include_archived:
            raise APIException(
                status_code=400,
                detail="contradictory filters",
                code=ErrorCode.VALIDATION_ERROR,
            )

        if cursor is not None and offset:
            raise APIException(
                status_code=400,
                detail="cursor_and_offset_mutually_exclusive",
                code=ErrorCode.VALIDATION_ERROR,
            )
        limit = max(1, min(limit, _MAX_LIMIT))

        query = self.database.db.query(ImportJob).filter(
            ImportJob.user_id == user.id
        )

        if status:
            query = query.filter(ImportJob.status == status)

        if archived_only:
            query = query.filter(ImportJob.archived_at.isnot(None))
        elif not include_archived:
            query = query.filter(ImportJob.archived_at.is_(None))

        see_all_mode = include_archived or archived_only

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
            if see_all_mode:
                cur_arch_ts = (
                    _NEG_INF
                    if cur_arch_ms is None
                    else datetime.fromtimestamp(cur_arch_ms / 1000, tz=UTC)
                )
                query = query.filter(
                    tuple_(
                        text(
                            "COALESCE(import_jobs.archived_at, "
                            "'-infinity'::timestamptz)"
                        ),
                        ImportJob.created_at,
                        ImportJob.id,
                    )
                    < tuple_(cur_arch_ts, cur_created, cur_id)
                )
            else:
                query = query.filter(
                    tuple_(ImportJob.created_at, ImportJob.id)
                    < tuple_(cur_created, cur_id)
                )

        total = query.count() if cursor is None else 0

        if see_all_mode:
            query = query.order_by(
                text(
                    "COALESCE(import_jobs.archived_at, "
                    "'-infinity'::timestamptz) DESC"
                ),
                ImportJob.created_at.desc(),
                ImportJob.id.desc(),
            )
        else:
            query = query.order_by(
                ImportJob.created_at.desc(), ImportJob.id.desc()
            )

        if cursor is not None:
            rows = query.limit(limit + 1).all()
            has_more = len(rows) > limit
            jobs = rows[:limit]
        else:
            jobs = query.offset(offset).limit(limit).all()
            has_more = offset + len(jobs) < total

        job_responses = []
        for job in jobs:
            job_responses.append(
                ListImportJobs.JobSummary(
                    id=str(job.id),
                    status=job.status,
                    source_type=job.source_type,
                    total_items=job.total_items,
                    succeeded_items=job.succeeded_items,
                    failed_items=job.failed_items,
                    pending_review_items=job.pending_review_items,
                    recipe_book_id=str(job.recipe_book_id),
                    created_at=job.created_at,
                    completed_at=job.completed_at,
                    archived_at=job.archived_at,
                )
            )

        next_cursor: str | None = None
        if has_more and jobs:
            last = jobs[-1]
            next_cursor = encode_cursor(
                datetime_to_ms(last.archived_at) if see_all_mode else None,
                datetime_to_ms(last.created_at),
                str(last.id),
            )

        headers = None
        if next_cursor:
            headers = {
                "Link": (
                    f'</v1/import-jobs?cursor={next_cursor}>; rel="next"'
                )
            }

        return success(
            data=ListImportJobs.Response(
                jobs=job_responses,
                total=total,
                has_more=has_more,
                next_cursor=next_cursor,
            ),
            headers=headers,
        )

    class JobSummary(BaseModel):
        id: str
        status: str
        source_type: str
        total_items: int
        succeeded_items: int
        failed_items: int
        pending_review_items: int
        recipe_book_id: str
        created_at: datetime
        completed_at: datetime | None = None
        archived_at: datetime | None = None

    class Response(BaseModel):
        jobs: list["ListImportJobs.JobSummary"]
        total: int
        has_more: bool
        next_cursor: str | None = None
