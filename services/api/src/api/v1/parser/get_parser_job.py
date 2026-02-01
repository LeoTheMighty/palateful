"""Get parser job endpoint."""

from datetime import datetime, timezone

from pydantic import BaseModel

from config import settings
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.parser_job import ParserJob
from utils.services.aws import AWSService


class GetParserJob(Endpoint):
    """Get parser job status and results."""

    def execute(self, job_id: str):
        """
        Get parser job status, syncing from AWS Batch if needed.

        Args:
            job_id: Parser job ID.

        Returns:
            Parser job status and extracted text if completed.
        """
        # Find job
        parser_job = self.database.find_by(ParserJob, id=job_id)
        if not parser_job:
            raise APIException(
                status_code=404,
                detail=f"Parser job with ID '{job_id}' not found",
                code=ErrorCode.NOT_FOUND,
            )

        # Verify ownership
        if parser_job.user_id != self.user.id:
            raise APIException(
                status_code=403,
                detail="You don't have permission to access this job",
                code=ErrorCode.FORBIDDEN,
            )

        # If job is not complete, sync status from AWS Batch
        if parser_job.status not in ("succeeded", "failed") and parser_job.batch_job_id:
            self._sync_batch_status(parser_job)

        return success(
            data=GetParserJob.Response(
                id=str(parser_job.id),
                batch_job_id=parser_job.batch_job_id,
                status=parser_job.status,
                input_s3_key=parser_job.input_s3_key,
                output_s3_key=parser_job.output_s3_key,
                extracted_text=parser_job.extracted_text,
                error_message=parser_job.error_message,
                created_at=parser_job.created_at.isoformat(),
                completed_at=parser_job.completed_at.isoformat() if parser_job.completed_at else None,
            )
        )

    def _sync_batch_status(self, parser_job: ParserJob) -> None:
        """Sync parser job status from AWS Batch."""
        aws = AWSService(
            region=settings.aws_region,
            parser_inputs_bucket=settings.parser_inputs_bucket,
            parser_outputs_bucket=settings.parser_outputs_bucket,
            batch_job_queue=settings.batch_job_queue,
            batch_job_definition=settings.batch_job_definition,
        )

        # Get Batch job status
        batch_job = aws.describe_batch_job(parser_job.batch_job_id)
        batch_status = batch_job.get("status", "UNKNOWN")
        new_status = aws.map_batch_status_to_parser_status(batch_status)

        # Update status
        parser_job.status = new_status

        # If succeeded, fetch results from S3
        if new_status == "succeeded" and parser_job.output_s3_key:
            try:
                result = aws.get_s3_object(parser_job.output_s3_key)
                parser_job.extracted_text = result.get("extracted_markdown", "")
                parser_job.completed_at = datetime.now(timezone.utc)
            except Exception as e:
                parser_job.error_message = f"Failed to fetch results: {str(e)}"
                parser_job.status = "failed"
                parser_job.completed_at = datetime.now(timezone.utc)

        # If failed, capture error message
        elif new_status == "failed":
            status_reason = batch_job.get("statusReason", "Unknown error")
            parser_job.error_message = status_reason
            parser_job.completed_at = datetime.now(timezone.utc)

        self.database.db.commit()

    class Response(BaseModel):
        id: str
        batch_job_id: str | None
        status: str
        input_s3_key: str | None
        output_s3_key: str | None
        extracted_text: str | None
        error_message: str | None
        created_at: str
        completed_at: str | None
