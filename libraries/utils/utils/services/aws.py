"""AWS service helpers for S3 and Batch operations."""

import json
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.config import Config


class AWSService:
    """Service for AWS S3 and Batch operations."""

    def __init__(
        self,
        region: str = "us-east-1",
        parser_inputs_bucket: str = "",
        parser_outputs_bucket: str = "",
        batch_job_queue: str = "",
        batch_job_definition: str = "",
    ):
        self.region = region
        self.parser_inputs_bucket = parser_inputs_bucket
        self.parser_outputs_bucket = parser_outputs_bucket
        self.batch_job_queue = batch_job_queue
        self.batch_job_definition = batch_job_definition

        config = Config(region_name=region)
        self._s3 = boto3.client("s3", config=config)
        self._batch = boto3.client("batch", config=config)

    def generate_presigned_upload_url(
        self,
        s3_key: str,
        content_type: str = "image/jpeg",
        expires_in: int = 3600,
    ) -> str:
        """
        Generate a presigned URL for uploading to S3.

        Args:
            s3_key: The S3 key for the object.
            content_type: The content type of the file.
            expires_in: URL expiration time in seconds.

        Returns:
            Presigned URL for PUT request.
        """
        return self._s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.parser_inputs_bucket,
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    def generate_presigned_download_url(
        self,
        s3_key: str,
        bucket: str | None = None,
        expires_in: int = 3600,
    ) -> str:
        """
        Generate a presigned URL for downloading from S3.

        Args:
            s3_key: The S3 key for the object.
            bucket: The bucket name (defaults to outputs bucket).
            expires_in: URL expiration time in seconds.

        Returns:
            Presigned URL for GET request.
        """
        return self._s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket or self.parser_outputs_bucket,
                "Key": s3_key,
            },
            ExpiresIn=expires_in,
        )

    def get_s3_object(self, s3_key: str, bucket: str | None = None) -> dict[str, Any]:
        """
        Get an object from S3 and parse it as JSON.

        Args:
            s3_key: The S3 key for the object.
            bucket: The bucket name (defaults to outputs bucket).

        Returns:
            Parsed JSON content.
        """
        response = self._s3.get_object(
            Bucket=bucket or self.parser_outputs_bucket,
            Key=s3_key,
        )
        return json.loads(response["Body"].read().decode("utf-8"))

    def submit_batch_job(
        self,
        job_name: str,
        input_s3_key: str,
        output_s3_key: str,
    ) -> str:
        """
        Submit a parser job to AWS Batch.

        Args:
            job_name: Name for the Batch job.
            input_s3_key: S3 key for input image.
            output_s3_key: S3 key for output JSON.

        Returns:
            Batch job ID.
        """
        input_uri = f"s3://{self.parser_inputs_bucket}/{input_s3_key}"
        output_uri = f"s3://{self.parser_outputs_bucket}/{output_s3_key}"

        response = self._batch.submit_job(
            jobName=job_name,
            jobQueue=self.batch_job_queue,
            jobDefinition=self.batch_job_definition,
            containerOverrides={
                "environment": [
                    {"name": "INPUT_S3_URI", "value": input_uri},
                    {"name": "OUTPUT_S3_URI", "value": output_uri},
                ],
            },
        )

        return response["jobId"]

    def describe_batch_job(self, job_id: str) -> dict[str, Any]:
        """
        Get the status of a Batch job.

        Args:
            job_id: AWS Batch job ID.

        Returns:
            Job details including status.
        """
        response = self._batch.describe_jobs(jobs=[job_id])
        if not response.get("jobs"):
            return {"status": "UNKNOWN"}
        return response["jobs"][0]

    def get_batch_job_status(self, job_id: str) -> str:
        """
        Get the status of a Batch job as a simple string.

        Batch statuses: SUBMITTED, PENDING, RUNNABLE, STARTING, RUNNING, SUCCEEDED, FAILED

        Args:
            job_id: AWS Batch job ID.

        Returns:
            Job status string.
        """
        job = self.describe_batch_job(job_id)
        return job.get("status", "UNKNOWN")

    def map_batch_status_to_parser_status(self, batch_status: str) -> str:
        """
        Map AWS Batch status to our parser job status.

        Args:
            batch_status: AWS Batch job status.

        Returns:
            Parser job status (pending, submitted, running, succeeded, failed).
        """
        mapping = {
            "SUBMITTED": "submitted",
            "PENDING": "submitted",
            "RUNNABLE": "submitted",
            "STARTING": "running",
            "RUNNING": "running",
            "SUCCEEDED": "succeeded",
            "FAILED": "failed",
            "UNKNOWN": "failed",
        }
        return mapping.get(batch_status, "pending")
