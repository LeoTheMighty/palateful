"""Watch parser batch task - safety-net polling for AWS Batch parser jobs.

The primary path for parser batch completion is now the direct callback from
the Batch container itself (POST /parser/batches/{id}/complete on run_job.py
exit). This watcher only exists to catch the failure mode where the container
crashes or is Spot-interrupted before it can make the callback.

Budget is 90 minutes — enough to cover worst-case Batch queue cold-start (often
20-30 minutes on a scale-to-zero GPU compute env) plus the 30-minute Batch
container timeout. If the callback fires sooner, the watcher becomes a no-op on
its next poll because complete_parser_batch is idempotent.
"""

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
from utils.models.parser_batch import ParserBatch
from utils.models.parser_job import ParserJob
from utils.services.aws import AWSService
from utils.services.celery import celery_app
from utils.services.parser_batch_completion import (
    TERMINAL_STATUSES,
    complete_parser_batch,
)
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 30
MAX_POLL_ATTEMPTS = 180  # 90 minutes — safety net only; callback is primary


class WatchParserBatchTask(BaseTask):
    """Safety-net poller for a ParserBatch's AWS Batch job.

    Runs complete_parser_batch on every poll; that function is idempotent and
    will exit early if the callback path has already handled the batch.
    """

    name = "watch_parser_batch_task"

    def execute(self, parser_batch_id: str, user_id: str = None, **kwargs):
        parser_batch = self.database.find_by(ParserBatch, id=parser_batch_id)
        if not parser_batch:
            logger.error("Parser batch not found: %s", parser_batch_id)
            return success({"error": "Parser batch not found"})

        if parser_batch.status in TERMINAL_STATUSES:
            logger.info(
                "Parser batch %s already %s; watcher is a no-op",
                parser_batch_id,
                parser_batch.status,
            )
            return success({"status": parser_batch.status})

        aws = AWSService(
            region=AWS_REGION,
            parser_inputs_bucket=PARSER_INPUTS_BUCKET,
            parser_outputs_bucket=PARSER_OUTPUTS_BUCKET,
            batch_job_queue=BATCH_JOB_QUEUE,
            batch_job_definition=BATCH_JOB_DEFINITION,
        )

        for attempt in range(MAX_POLL_ATTEMPTS):
            # Re-fetch each iteration so we notice the callback path finishing
            parser_batch = self.database.find_by(ParserBatch, id=parser_batch_id)
            if parser_batch.status in TERMINAL_STATUSES:
                logger.info(
                    "Parser batch %s became %s between polls; watcher exiting",
                    parser_batch_id,
                    parser_batch.status,
                )
                return success({"status": parser_batch.status})

            final_status = complete_parser_batch(self.database, aws, parser_batch)
            logger.info(
                "Safety-net poll %d/%d for parser batch %s: status=%s",
                attempt + 1,
                MAX_POLL_ATTEMPTS,
                parser_batch_id,
                final_status,
            )

            if final_status in TERMINAL_STATUSES:
                return success(
                    {
                        "parser_batch_id": parser_batch_id,
                        "status": final_status,
                    }
                )

            if attempt < MAX_POLL_ATTEMPTS - 1:
                time.sleep(POLL_INTERVAL_SECONDS)

        # Timed out — the callback never fired AND AWS Batch never reported terminal
        # within 90 minutes. Mark the batch failed so the user can retry.
        from utils.services.parser_batch_completion import (
            _create_failure_activity,
            _mark_failed,
        )

        _mark_failed(self.database, parser_batch, "Watcher timed out after 90 minutes")
        parser_jobs = (
            self.database.db.query(ParserJob)
            .filter(ParserJob.parser_batch_id == parser_batch.id)
            .all()
        )
        for pj in parser_jobs:
            if pj.status not in TERMINAL_STATUSES:
                pj.status = "failed"
                pj.error_message = "Watcher timed out"
                pj.completed_at = datetime.now(UTC)
        self.database.db.commit()
        _create_failure_activity(self.database, parser_batch, "OCR processing timed out")

        return success(
            {
                "parser_batch_id": parser_batch_id,
                "status": "failed",
                "error": "timeout",
            }
        )


# Register task with Celery
watch_parser_batch_task = celery_app.register_task(WatchParserBatchTask())
