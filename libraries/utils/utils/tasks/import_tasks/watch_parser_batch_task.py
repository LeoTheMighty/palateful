"""Watch parser batch task - polls AWS Batch for a parser_batch and fans out
to one ImportJob per group_index when OCR completes.

This is the multi-image / multi-recipe successor to WatchParserJobTask:
- Each ParserBatch corresponds to one AWS Batch manifest job (single batch_job_id)
- N parser jobs in the batch share that batch_job_id
- Jobs sharing a `group_index` represent pages of the same recipe and are merged
  into a single ImportItem with concatenated OCR text
"""

import logging
import time
from collections import defaultdict
from datetime import UTC, datetime

from utils.api.endpoint import success
from utils.constants import (
    AWS_REGION,
    BATCH_JOB_DEFINITION,
    BATCH_JOB_QUEUE,
    PARSER_INPUTS_BUCKET,
    PARSER_OUTPUTS_BUCKET,
    STAGE_PARSED,
)
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.parser_batch import ParserBatch
from utils.models.parser_job import ParserJob
from utils.services.aws import AWSService
from utils.services.celery import celery_app
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 30
MAX_POLL_ATTEMPTS = 40  # 20 minutes
PAGE_SEPARATOR = "\n\n--- page break ---\n\n"

TERMINAL_STATUSES = ("succeeded", "failed", "partial")


class WatchParserBatchTask(BaseTask):
    """Poll a ParserBatch's shared AWS Batch job and continue the import pipeline.

    On success, fans out to one ImportJob per group_index, with each ImportItem
    containing the concatenated OCR text from all jobs sharing that group_index.
    """

    name = "watch_parser_batch_task"

    def execute(self, parser_batch_id: str, user_id: str = None, **kwargs):
        parser_batch = self.database.find_by(ParserBatch, id=parser_batch_id)
        if not parser_batch:
            logger.error("Parser batch not found: %s", parser_batch_id)
            return success({"error": "Parser batch not found"})

        # Idempotency: terminal batches are no-ops
        if parser_batch.status in TERMINAL_STATUSES:
            logger.info(
                "Parser batch %s already %s; no-op",
                parser_batch_id,
                parser_batch.status,
            )
            return success({"status": parser_batch.status})

        parser_jobs = (
            self.database.db.query(ParserJob)
            .filter(ParserJob.parser_batch_id == parser_batch.id)
            .all()
        )
        if not parser_jobs:
            logger.error(
                "Parser batch %s has no parser jobs", parser_batch_id
            )
            self._mark_failed(parser_batch, "No parser jobs in batch")
            return success({"status": "failed", "error": "no jobs"})

        batch_job_id = next(
            (pj.batch_job_id for pj in parser_jobs if pj.batch_job_id), None
        )
        if not batch_job_id:
            logger.error(
                "Parser batch %s has no batch_job_id on any job",
                parser_batch_id,
            )
            self._mark_failed(parser_batch, "No AWS Batch job ID")
            return success({"status": "failed", "error": "no batch_job_id"})

        aws = AWSService(
            region=AWS_REGION,
            parser_inputs_bucket=PARSER_INPUTS_BUCKET,
            parser_outputs_bucket=PARSER_OUTPUTS_BUCKET,
            batch_job_queue=BATCH_JOB_QUEUE,
            batch_job_definition=BATCH_JOB_DEFINITION,
        )

        for attempt in range(MAX_POLL_ATTEMPTS):
            batch_job = aws.describe_batch_job(batch_job_id)
            batch_status = batch_job.get("status", "UNKNOWN")
            new_status = aws.map_batch_status_to_parser_status(batch_status)

            logger.info(
                "Poll %d/%d for parser batch %s: batch=%s, mapped=%s",
                attempt + 1,
                MAX_POLL_ATTEMPTS,
                parser_batch_id,
                batch_status,
                new_status,
            )

            if new_status in ("running", "submitted"):
                if parser_batch.status != new_status:
                    parser_batch.status = new_status
                for pj in parser_jobs:
                    if pj.status not in TERMINAL_STATUSES:
                        pj.status = new_status
                self.database.db.commit()

            if new_status == "succeeded":
                self._handle_success(parser_batch, parser_jobs, aws)
                return success(
                    {
                        "parser_batch_id": parser_batch_id,
                        "status": parser_batch.status,
                    }
                )

            if new_status == "failed":
                self._handle_total_failure(
                    parser_batch, parser_jobs, batch_job
                )
                return success(
                    {
                        "parser_batch_id": parser_batch_id,
                        "status": "failed",
                    }
                )

            if attempt < MAX_POLL_ATTEMPTS - 1:
                time.sleep(POLL_INTERVAL_SECONDS)

        # Timed out
        self._mark_failed(parser_batch, "Watcher timed out after 20 minutes")
        for pj in parser_jobs:
            if pj.status not in TERMINAL_STATUSES:
                pj.status = "failed"
                pj.error_message = "Watcher timed out"
                pj.completed_at = datetime.now(UTC)
        self.database.db.commit()
        self._create_failure_activity(parser_batch, "OCR processing timed out")

        return success(
            {
                "parser_batch_id": parser_batch_id,
                "status": "failed",
                "error": "timeout",
            }
        )

    # ------------------------------------------------------------------
    # Success path
    # ------------------------------------------------------------------

    def _handle_success(
        self,
        parser_batch: ParserBatch,
        parser_jobs: list[ParserJob],
        aws: AWSService,
    ) -> None:
        """Read S3 output for every job, then fan out to ImportJobs by group_index."""
        now = datetime.now(UTC)
        succeeded_jobs: list[ParserJob] = []
        failed_jobs: list[ParserJob] = []

        for pj in parser_jobs:
            try:
                result = aws.get_s3_object(pj.output_s3_key)
                extracted_text = result.get("extracted_markdown", "") or ""
                pj.extracted_text = extracted_text
                pj.status = "succeeded"
                pj.completed_at = now
                succeeded_jobs.append(pj)
            except Exception as e:
                logger.exception(
                    "Failed to fetch S3 results for parser job %s", pj.id
                )
                pj.status = "failed"
                pj.error_message = f"Failed to fetch results: {str(e)}"
                pj.completed_at = now
                failed_jobs.append(pj)

        self.database.db.commit()

        if not succeeded_jobs:
            self._mark_failed(parser_batch, "All OCR jobs failed")
            self._create_failure_activity(parser_batch, "All OCR jobs failed")
            return

        # Group succeeded jobs by group_index
        groups: dict[int, list[ParserJob]] = defaultdict(list)
        for pj in succeeded_jobs:
            groups[pj.group_index].append(pj)

        # Need a recipe_book_id to create ImportJobs; without one, we're done
        if not parser_batch.recipe_book_id:
            logger.info(
                "Parser batch %s succeeded but no recipe_book_id; skipping import.",
                parser_batch.id,
            )
            parser_batch.status = (
                "succeeded" if not failed_jobs else "partial"
            )
            parser_batch.completed_at = now
            self.database.db.commit()
            return

        from utils.tasks.import_tasks.parse_source_task import (
            parse_source_task,
        )

        for group_index, jobs in sorted(groups.items()):
            jobs_in_order = sorted(jobs, key=lambda j: j.created_at)
            concatenated_text = PAGE_SEPARATOR.join(
                j.extracted_text or "" for j in jobs_in_order
            )
            s3_keys = [j.input_s3_key for j in jobs_in_order if j.input_s3_key]

            import_job = ImportJob(
                user_id=parser_batch.user_id,
                recipe_book_id=parser_batch.recipe_book_id,
                status="pending",
                source_type="photo",
                total_items=1,
                parser_batch_id=parser_batch.id,
            )
            self.database.create(import_job)

            import_item = ImportItem(
                import_job_id=import_job.id,
                source_type="photo",
                status="pending",
                last_successful_stage=STAGE_PARSED,
                raw_data={
                    "text": concatenated_text,
                    "s3_keys": s3_keys,
                    "group_index": group_index,
                },
            )
            self.database.create(import_item)

            # Link parser jobs back to the import job for traceability
            for j in jobs_in_order:
                j.import_job_id = import_job.id

            self.database.db.commit()

            parse_source_task.delay(
                str(import_job.id),
                user_id=str(parser_batch.user_id),
            )

            logger.info(
                "Created ImportJob %s for parser batch %s group %d (%d page(s))",
                import_job.id,
                parser_batch.id,
                group_index,
                len(jobs_in_order),
            )

        if failed_jobs:
            parser_batch.status = "partial"
            parser_batch.error_message = (
                f"{len(failed_jobs)} of {len(parser_jobs)} OCR jobs failed"
            )
        else:
            parser_batch.status = "succeeded"
        parser_batch.completed_at = now
        self.database.db.commit()

    # ------------------------------------------------------------------
    # Failure paths
    # ------------------------------------------------------------------

    def _handle_total_failure(
        self,
        parser_batch: ParserBatch,
        parser_jobs: list[ParserJob],
        batch_job: dict,
    ) -> None:
        status_reason = batch_job.get("statusReason", "Unknown error")
        now = datetime.now(UTC)
        for pj in parser_jobs:
            if pj.status not in TERMINAL_STATUSES:
                pj.status = "failed"
                pj.error_message = status_reason
                pj.completed_at = now
        self._mark_failed(parser_batch, status_reason)
        self.database.db.commit()
        self._create_failure_activity(parser_batch, status_reason)

    def _mark_failed(self, parser_batch: ParserBatch, reason: str) -> None:
        parser_batch.status = "failed"
        parser_batch.error_message = reason
        parser_batch.completed_at = datetime.now(UTC)
        self.database.db.commit()

    def _create_failure_activity(
        self, parser_batch: ParserBatch, reason: str
    ) -> None:
        try:
            from utils.services.activity_service import create_activity

            create_activity(
                self.database.db,
                user_id=parser_batch.user_id,
                activity_type="parser_job_failed",
                title="Photo OCR failed",
                subtitle=reason[:200] if reason else "Unknown error",
                metadata={"parser_batch_id": str(parser_batch.id)},
            )
            self.database.db.commit()
        except Exception:
            logger.exception(
                "Failed to create failure activity for parser batch %s",
                parser_batch.id,
            )


# Register task with Celery
watch_parser_batch_task = celery_app.register_task(WatchParserBatchTask())
