"""Parser batch completion logic.

Pure functions shared by WatchParserBatchTask (the polling fallback) and the
callback endpoint hit by the Batch container itself. Both entry points converge
on complete_parser_batch, which is idempotent: if the batch is already terminal
or has already spawned ImportJobs, it returns without mutating anything.

Authoritative state comes from AWS Batch — never from caller-supplied data.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime

from utils.constants import STAGE_PARSED
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.parser_batch import ParserBatch
from utils.models.parser_job import ParserJob
from utils.services.aws import AWSService
from utils.services.database import Database

logger = logging.getLogger(__name__)

PAGE_SEPARATOR = "\n\n--- page break ---\n\n"
TERMINAL_STATUSES = ("succeeded", "failed", "partial")


def complete_parser_batch(
    database: Database,
    aws: AWSService,
    parser_batch: ParserBatch,
) -> str:
    """Move a parser batch to a terminal state based on AWS Batch's view of the job.

    Re-queries AWS Batch for the authoritative job status, then:
    - If still running, returns "running" without mutation.
    - If succeeded, reads OCR output for each ParserJob, groups by group_index,
      creates one ImportJob + ImportItem per group, dispatches parse_source_task.
    - If failed, marks the batch + all non-terminal jobs failed, fires activity.

    Idempotent: if parser_batch is already terminal, returns its status with no
    side effects.

    Returns the final parser_batch.status value.
    """
    if parser_batch.status in TERMINAL_STATUSES:
        logger.info(
            "Parser batch %s already %s; complete_parser_batch is a no-op",
            parser_batch.id,
            parser_batch.status,
        )
        return parser_batch.status

    parser_jobs = (
        database.db.query(ParserJob)
        .filter(ParserJob.parser_batch_id == parser_batch.id)
        .all()
    )
    if not parser_jobs:
        _mark_failed(database, parser_batch, "No parser jobs in batch")
        _create_failure_activity(database, parser_batch, "No parser jobs in batch")
        return "failed"

    batch_job_id = next(
        (pj.batch_job_id for pj in parser_jobs if pj.batch_job_id), None
    )
    if not batch_job_id:
        _mark_failed(database, parser_batch, "No AWS Batch job ID")
        _create_failure_activity(database, parser_batch, "No AWS Batch job ID")
        return "failed"

    batch_job = aws.describe_batch_job(batch_job_id)
    batch_status = batch_job.get("status", "UNKNOWN")
    mapped = aws.map_batch_status_to_parser_status(batch_status)

    if mapped == "succeeded":
        _handle_success(database, aws, parser_batch, parser_jobs)
        return parser_batch.status

    if mapped == "failed":
        _handle_total_failure(database, parser_batch, parser_jobs, batch_job)
        return "failed"

    # Still running / submitted — don't touch anything
    logger.info(
        "Parser batch %s AWS status=%s (mapped=%s); leaving untouched",
        parser_batch.id,
        batch_status,
        mapped,
    )
    return mapped


def _handle_success(
    database: Database,
    aws: AWSService,
    parser_batch: ParserBatch,
    parser_jobs: list[ParserJob],
) -> None:
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
            logger.exception("Failed to fetch S3 results for parser job %s", pj.id)
            pj.status = "failed"
            pj.error_message = f"Failed to fetch results: {str(e)}"
            pj.completed_at = now
            failed_jobs.append(pj)

    database.db.commit()

    if not succeeded_jobs:
        _mark_failed(database, parser_batch, "All OCR jobs failed")
        _create_failure_activity(database, parser_batch, "All OCR jobs failed")
        return

    groups: dict[int, list[ParserJob]] = defaultdict(list)
    for pj in succeeded_jobs:
        groups[pj.group_index].append(pj)

    if not parser_batch.recipe_book_id:
        logger.info(
            "Parser batch %s succeeded but no recipe_book_id; skipping import.",
            parser_batch.id,
        )
        parser_batch.status = "succeeded" if not failed_jobs else "partial"
        parser_batch.completed_at = now
        database.db.commit()
        return

    # Guard against double-fan-out if two callers race
    existing_import = (
        database.db.query(ImportJob)
        .filter(ImportJob.parser_batch_id == parser_batch.id)
        .first()
    )
    if existing_import:
        logger.info(
            "Parser batch %s already has ImportJob %s; skipping fan-out",
            parser_batch.id,
            existing_import.id,
        )
        parser_batch.status = "succeeded" if not failed_jobs else "partial"
        parser_batch.completed_at = now
        database.db.commit()
        return

    from utils.tasks.import_tasks.parse_source_task import parse_source_task

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
        database.create(import_job)

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
        database.create(import_item)

        for j in jobs_in_order:
            j.import_job_id = import_job.id

        database.db.commit()

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
    database.db.commit()


def _handle_total_failure(
    database: Database,
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
    _mark_failed(database, parser_batch, status_reason)
    database.db.commit()
    _create_failure_activity(database, parser_batch, status_reason)


def _mark_failed(database: Database, parser_batch: ParserBatch, reason: str) -> None:
    parser_batch.status = "failed"
    parser_batch.error_message = reason
    parser_batch.completed_at = datetime.now(UTC)
    database.db.commit()


def _create_failure_activity(
    database: Database, parser_batch: ParserBatch, reason: str
) -> None:
    try:
        from utils.services.activity_service import create_activity

        create_activity(
            database.db,
            user_id=parser_batch.user_id,
            activity_type="parser_job_failed",
            title="Photo OCR failed",
            subtitle=reason[:200] if reason else "Unknown error",
            metadata={"parser_batch_id": str(parser_batch.id)},
        )
        database.db.commit()
    except Exception:
        logger.exception(
            "Failed to create failure activity for parser batch %s",
            parser_batch.id,
        )
