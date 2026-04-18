"""List import jobs endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_job import ImportJob
from utils.models.user import User


class ListImportJobs(Endpoint):
    """List all import jobs for the current user."""

    def execute(
        self,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
        include_archived: bool = False,
        archived_only: bool = False,
    ):
        """List import jobs for the authenticated user.

        ``include_archived`` / ``archived_only`` back the Imports-tab
        See-all footer (ahr-5). Default list (both false) keeps the
        existing behavior of hiding archived rows alongside dismissed
        rows. ``archived_only=true`` returns only archived rows and
        implies ``include_archived=true`` — the combination
        ``archived_only=true & include_archived=false`` is a contradiction
        that returns 400.
        """
        user: User = self.user

        if archived_only and not include_archived:
            raise APIException(
                status_code=400,
                detail="contradictory filters",
                code=ErrorCode.VALIDATION_ERROR,
            )

        query = self.database.db.query(ImportJob).filter(
            ImportJob.user_id == user.id
        )

        if status:
            query = query.filter(ImportJob.status == status)

        if archived_only:
            query = query.filter(ImportJob.archived_at.isnot(None))
        elif not include_archived:
            query = query.filter(ImportJob.archived_at.is_(None))

        total = query.count()

        jobs = (
            query.order_by(ImportJob.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

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

        return success(
            data=ListImportJobs.Response(
                jobs=job_responses,
                total=total,
                has_more=offset + len(jobs) < total,
            )
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
