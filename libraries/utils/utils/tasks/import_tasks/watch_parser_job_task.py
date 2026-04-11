"""Watch parser job task - polls AWS Batch and continues import pipeline on success."""

import logging
import time
from datetime import UTC, datetime

from utils.api.endpoint import success
from utils.constants import (
    AWS_REGION,
    BATCH_JOB_DEFINITION,
    BATCH_JOB_QUEUE,
    PARSER_INPUTS_BUCKET,
    PARSER_OUTPUTS_BUCKET,
)
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.parser_job import ParserJob
from utils.services.aws import AWSService
from utils.services.celery import celery_app
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

# Polling configuration
POLL_INTERVAL_SECONDS = 30
MAX_POLL_ATTEMPTS = 40  # 40 * 30s = 20 minutes max


class WatchParserJobTask(BaseTask):
    """Watch an AWS Batch parser job and continue the import pipeline when it completes.

    This task polls Batch for status every 30 seconds. When the OCR job succeeds,
    it reads the S3 output, creates an ImportJob + ImportItem, and dispatches
    parse_source_task to continue the pipeline. When it fails, it updates the
    ParserJob status and creates a failure activity.
    """

    name = "watch_parser_job_task"

    def execute(self, parser_job_id: str, user_id: str = None, **kwargs):
        """Poll AWS Batch for parser job completion and continue the pipeline.

        Args:
            parser_job_id: The ParserJob ID to watch.
            user_id: The user who owns the job (passed via kwargs by BaseTask).

        Returns:
            Success response with final status.
        """
        parser_job = self.database.find_by(ParserJob, id=parser_job_id)
        if not parser_job:
            logger.error("Parser job not found: %s", parser_job_id)
            return success({"error": "Parser job not found"})

        if not parser_job.batch_job_id:
            logger.error("Parser job %s has no batch_job_id", parser_job_id)
            return success({"error": "No batch job ID"})

        # Already terminal or already has an import job
        if parser_job.status in ("succeeded", "failed"):
            logger.info("Parser job %s already %s", parser_job_id, parser_job.status)
            return success({"status": parser_job.status})

        if parser_job.import_job_id:
            logger.info("Parser job %s already has import job %s", parser_job_id, parser_job.import_job_id)
            return success({"status": parser_job.status, "import_job_id": str(parser_job.import_job_id)})

        aws = AWSService(
            region=AWS_REGION,
            parser_inputs_bucket=PARSER_INPUTS_BUCKET,
            parser_outputs_bucket=PARSER_OUTPUTS_BUCKET,
            batch_job_queue=BATCH_JOB_QUEUE,
            batch_job_definition=BATCH_JOB_DEFINITION,
        )

        # Poll loop
        for attempt in range(MAX_POLL_ATTEMPTS):
            batch_job = aws.describe_batch_job(parser_job.batch_job_id)
            batch_status = batch_job.get("status", "UNKNOWN")
            new_status = aws.map_batch_status_to_parser_status(batch_status)

            logger.info(
                "Poll %d/%d for parser job %s: batch=%s, mapped=%s",
                attempt + 1, MAX_POLL_ATTEMPTS, parser_job_id, batch_status, new_status,
            )

            # Update intermediate status
            if new_status in ("running", "submitted"):
                parser_job.status = new_status
                self.database.db.commit()

            if new_status == "succeeded":
                self._handle_success(parser_job, aws)
                return success({
                    "parser_job_id": parser_job_id,
                    "status": "succeeded",
                    "import_job_id": str(parser_job.import_job_id) if parser_job.import_job_id else None,
                })

            if new_status == "failed":
                self._handle_failure(parser_job, batch_job)
                return success({
                    "parser_job_id": parser_job_id,
                    "status": "failed",
                })

            # Wait before next poll (skip on last attempt)
            if attempt < MAX_POLL_ATTEMPTS - 1:
                time.sleep(POLL_INTERVAL_SECONDS)

        # Timed out
        parser_job.status = "failed"
        parser_job.error_message = "Watcher timed out after 20 minutes"
        parser_job.completed_at = datetime.now(UTC)
        self.database.db.commit()

        self._create_failure_activity(parser_job, "OCR processing timed out")

        return success({
            "parser_job_id": parser_job_id,
            "status": "failed",
            "error": "timeout",
        })

    def _handle_success(self, parser_job: ParserJob, aws: AWSService) -> None:
        """Handle successful Batch job: read S3 output, create ImportJob + ImportItem."""
        # Read S3 output
        try:
            result = aws.get_s3_object(parser_job.output_s3_key)
            extracted_text = result.get("extracted_markdown", "")
        except Exception as e:
            logger.exception("Failed to fetch S3 results for parser job %s", parser_job.id)
            parser_job.status = "failed"
            parser_job.error_message = f"Failed to fetch results: {str(e)}"
            parser_job.completed_at = datetime.now(UTC)
            self.database.db.commit()
            self._create_failure_activity(parser_job, "Failed to read OCR results")
            return

        # Update parser job
        parser_job.extracted_text = extracted_text
        parser_job.status = "succeeded"
        parser_job.completed_at = datetime.now(UTC)
        self.database.db.commit()

        # If no recipe_book_id, we're done (old-style client-driven flow)
        if not parser_job.recipe_book_id:
            logger.info("Parser job %s succeeded but no recipe_book_id; skipping import.", parser_job.id)
            return

        # Guard: don't create duplicate import jobs
        if parser_job.import_job_id:
            logger.info("Parser job %s already has import job %s; skipping.", parser_job.id, parser_job.import_job_id)
            return

        # Create ImportJob
        import_job = ImportJob(
            user_id=parser_job.user_id,
            recipe_book_id=parser_job.recipe_book_id,
            status="pending",
            source_type="photo",
            total_items=1,
        )
        self.database.create(import_job)

        # Create ImportItem with the extracted text
        import_item = ImportItem(
            import_job_id=import_job.id,
            source_type="photo",
            status="pending",
            raw_data={"text": extracted_text},
        )
        self.database.create(import_item)

        # Link parser job to import job
        parser_job.import_job_id = import_job.id
        self.database.db.commit()

        logger.info(
            "Created import job %s and item %s for parser job %s",
            import_job.id, import_item.id, parser_job.id,
        )

        # Dispatch parse_source_task to continue the pipeline
        from utils.tasks.import_tasks.parse_source_task import parse_source_task
        parse_source_task.delay(
            str(import_job.id),
            user_id=str(parser_job.user_id),
        )

    def _handle_failure(self, parser_job: ParserJob, batch_job: dict) -> None:
        """Handle failed Batch job."""
        status_reason = batch_job.get("statusReason", "Unknown error")
        parser_job.status = "failed"
        parser_job.error_message = status_reason
        parser_job.completed_at = datetime.now(UTC)
        self.database.db.commit()

        self._create_failure_activity(parser_job, status_reason)

    def _create_failure_activity(self, parser_job: ParserJob, reason: str) -> None:
        """Create a user-facing activity for parser job failure."""
        try:
            from utils.services.activity_service import create_activity
            create_activity(
                self.database.db,
                user_id=parser_job.user_id,
                activity_type="parser_job_failed",
                title="Photo OCR failed",
                subtitle=reason[:200] if reason else "Unknown error",
                metadata={"parser_job_id": str(parser_job.id)},
            )
            self.database.db.commit()
        except Exception:
            logger.exception("Failed to create failure activity for parser job %s", parser_job.id)


# Register task with Celery
watch_parser_job_task = celery_app.register_task(WatchParserJobTask())
