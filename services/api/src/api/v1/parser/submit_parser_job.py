"""Submit parser job endpoint."""

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from config import settings
from utils.api.endpoint import Endpoint, success
from utils.models.parser_job import ParserJob
from utils.services.aws import AWSService


class SubmitParserJob(Endpoint):
    """Submit an OCR parsing job to AWS Batch."""

    def execute(self, params: "SubmitParserJob.Params"):
        """
        Submit a parser job to AWS Batch.

        Args:
            params: Request parameters with S3 key of uploaded image.

        Returns:
            Created parser job with job ID and status.
        """
        # Generate output S3 key
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        output_s3_key = f"results/{self.user.id}/{timestamp}_{unique_id}.json"

        # Create parser job record
        parser_job = ParserJob(
            user_id=self.user.id,
            status="pending",
            input_s3_key=params.s3_key,
            output_s3_key=output_s3_key,
        )
        self.database.create(parser_job)
        self.database.db.commit()
        self.database.db.refresh(parser_job)

        # Submit to AWS Batch
        aws = AWSService(
            region=settings.aws_region,
            parser_inputs_bucket=settings.parser_inputs_bucket,
            parser_outputs_bucket=settings.parser_outputs_bucket,
            batch_job_queue=settings.batch_job_queue,
            batch_job_definition=settings.batch_job_definition,
        )

        job_name = f"parser-{str(parser_job.id)[:8]}"
        batch_job_id = aws.submit_batch_job(
            job_name=job_name,
            input_s3_key=params.s3_key,
            output_s3_key=output_s3_key,
        )

        # Update job with Batch job ID and status
        parser_job.batch_job_id = batch_job_id
        parser_job.status = "submitted"
        self.database.db.commit()

        return success(
            data=SubmitParserJob.Response(
                id=str(parser_job.id),
                batch_job_id=batch_job_id,
                status=parser_job.status,
                input_s3_key=parser_job.input_s3_key,
                created_at=parser_job.created_at.isoformat(),
            ),
            status=201,
        )

    class Params(BaseModel):
        s3_key: str

    class Response(BaseModel):
        id: str
        batch_job_id: str
        status: str
        input_s3_key: str
        created_at: str
