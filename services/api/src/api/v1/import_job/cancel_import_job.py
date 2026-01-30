"""Cancel import job endpoint."""

from datetime import UTC, datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class CancelImportJob(Endpoint):
    """Cancel an import job."""

    def execute(self, job_id: str):
        """
        Cancel an import job.

        Args:
            job_id: The import job ID.

        Returns:
            Updated import job data.
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

        # Check access - must be owner or the user who started the import
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=job.recipe_book_id,
        )
        if not membership or (membership.role != "owner" and job.user_id != user.id):
            raise APIException(
                status_code=403,
                detail="You don't have permission to cancel this import job",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        # Validate status
        if job.status in ("completed", "cancelled"):
            raise APIException(
                status_code=400,
                detail=f"Cannot cancel job in {job.status} status",
                code=ErrorCode.IMPORT_JOB_INVALID_STATUS,
            )

        # Update status
        job.status = "cancelled"
        job.completed_at = datetime.now(UTC)
        self.database.db.commit()

        return success(
            data=CancelImportJob.Response(
                id=str(job.id),
                status=job.status,
                completed_at=job.completed_at,
            )
        )

    class Response(BaseModel):
        id: str
        status: str
        completed_at: datetime
