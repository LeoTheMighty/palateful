"""Submit batch parser job endpoint."""

import uuid
from datetime import UTC, datetime

from config import settings
from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.parser_job import ParserJob
from utils.services.aws import AWSService


class SubmitBatchParserJob(Endpoint):
    """Submit a batch OCR parsing job to AWS Batch for multiple images."""

    def execute(self, params: "SubmitBatchParserJob.Params"):
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        batch_id = str(uuid.uuid4())[:8]

        aws = AWSService(
            region=settings.aws_region,
            parser_inputs_bucket=settings.parser_inputs_bucket,
            parser_outputs_bucket=settings.parser_outputs_bucket,
            batch_job_queue=settings.batch_job_queue,
            batch_job_definition=settings.batch_job_definition,
        )

        # Create a ParserJob record and manifest item for each image
        items = []
        parser_jobs = []
        for i, s3_key in enumerate(params.s3_keys):
            unique_id = str(uuid.uuid4())[:8]
            output_s3_key = f"results/{self.user.id}/{timestamp}_{unique_id}.json"

            parser_job = ParserJob(
                user_id=self.user.id,
                status="pending",
                input_s3_key=s3_key,
                output_s3_key=output_s3_key,
            )
            self.database.create(parser_job)
            parser_jobs.append(parser_job)

            items.append({
                "input_s3_key": s3_key,
                "output_s3_key": output_s3_key,
            })

        self.database.db.commit()
        for pj in parser_jobs:
            self.database.db.refresh(pj)

        # Submit as a single Batch job with a manifest
        manifest_s3_key = f"manifests/{self.user.id}/{timestamp}_{batch_id}.json"
        job_name = f"parser-batch-{batch_id}"

        batch_job_id = aws.submit_batch_manifest_job(
            job_name=job_name,
            items=items,
            manifest_s3_key=manifest_s3_key,
        )

        # Update all parser jobs with the shared Batch job ID
        for pj in parser_jobs:
            pj.batch_job_id = batch_job_id
            pj.status = "submitted"
        self.database.db.commit()

        return success(
            data=SubmitBatchParserJob.Response(
                batch_job_id=batch_job_id,
                jobs=[
                    SubmitBatchParserJob.JobInfo(
                        id=str(pj.id),
                        input_s3_key=pj.input_s3_key,
                    )
                    for pj in parser_jobs
                ],
            ),
            status=201,
        )

    class Params(BaseModel):
        s3_keys: list[str]

    class JobInfo(BaseModel):
        id: str
        input_s3_key: str

    class Response(BaseModel):
        batch_job_id: str
        jobs: list["SubmitBatchParserJob.JobInfo"]
