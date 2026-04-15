"""List import jobs endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.import_job import ImportJob
from utils.models.user import User


class ListImportJobs(Endpoint):
    """List all import jobs for the current user."""

    def execute(self, status: str | None = None, limit: int = 20, offset: int = 0):
        """
        List import jobs for the authenticated user.

        Args:
            status: Optional status filter.
            limit: Maximum items to return.
            offset: Offset for pagination.

        Returns:
            List of import jobs with total count.
        """
        user: User = self.user

        # Build query
        query = self.database.db.query(ImportJob).filter(
            ImportJob.user_id == user.id
        )

        if status:
            query = query.filter(ImportJob.status == status)

        # Get total count
        total = query.count()

        # Apply pagination
        jobs = query.order_by(ImportJob.created_at.desc()).offset(offset).limit(limit).all()

        # Build response
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

    class Response(BaseModel):
        jobs: list["ListImportJobs.JobSummary"]
        total: int
        has_more: bool
