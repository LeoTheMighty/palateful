"""Get import job endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class GetImportJob(Endpoint):
    """Get import job details and status."""

    def execute(self, job_id: str):
        """
        Get import job details.

        Args:
            job_id: The import job ID.

        Returns:
            Import job data.
        """
        user: User = self.user

        # Load import job
        job = self.database.find_by(ImportJob, id=job_id)
        if not job:
            raise APIException(
                status_code=404,
                detail=f"Import job with ID '{job_id}' not found",
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
                detail="You don't have access to this import job",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        return success(
            data=GetImportJob.Response(
                id=str(job.id),
                status=job.status,
                source_type=job.source_type,
                source_filename=job.source_filename,
                total_items=job.total_items,
                processed_items=job.processed_items,
                succeeded_items=job.succeeded_items,
                failed_items=job.failed_items,
                pending_review_items=job.pending_review_items,
                total_ai_cost_cents=job.total_ai_cost_cents,
                recipe_book_id=str(job.recipe_book_id),
                started_at=job.started_at,
                completed_at=job.completed_at,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
        )

    class Response(BaseModel):
        id: str
        status: str
        source_type: str
        source_filename: str | None = None
        total_items: int
        processed_items: int
        succeeded_items: int
        failed_items: int
        pending_review_items: int
        total_ai_cost_cents: int
        recipe_book_id: str
        started_at: datetime | None = None
        completed_at: datetime | None = None
        created_at: datetime
        updated_at: datetime
