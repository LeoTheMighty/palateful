"""Parse source task - parses import source and creates ImportItem records."""

import logging
from datetime import UTC, datetime

from utils.api.endpoint import success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.services.celery import celery_app
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)


class ParseSourceTask(BaseTask):
    """Parse import source and create ImportItem records.

    This task handles the initial parsing of import sources:
    - url_list: Creates one ImportItem per URL
    - spreadsheet: Parses CSV/Excel and creates items per row (future)
    - pdf: Detects recipe boundaries and creates items (future)
    """

    name = "parse_source_task"

    def execute(self, import_job_id: str):
        """Parse the import source and create ImportItem records.

        Args:
            import_job_id: The ID of the import job to process.

        Returns:
            Success response with job statistics.
        """
        # Load import job
        job = self.database.find_by(ImportJob, id=import_job_id)
        if not job:
            logger.error("Import job not found: %s", import_job_id)
            return success({"error": "Import job not found"})

        # Update job status
        job.status = "processing"
        job.started_at = datetime.now(UTC)
        self.database.db.commit()

        try:
            if job.source_type == "url_list":
                items_created = self._parse_url_list(job)
            elif job.source_type == "url":
                items_created = self._parse_single_url(job)
            elif job.source_type in ("photo", "text", "spreadsheet"):
                # Items are already created by StartImport with text in raw_data.
                # total_items is already set by StartImport, so just read the count.
                items_created = job.total_items
            else:
                job.status = "failed"
                self.database.db.commit()
                return success({
                    "error": f"Unsupported source type: {job.source_type}",
                    "error_code": ErrorCode.IMPORT_INVALID_SOURCE_TYPE.value,
                })

            # Update job totals
            job.total_items = items_created
            self.database.db.commit()

            # Fan out to ExtractRecipeTask
            self._dispatch_extraction_tasks(job)

            return success({
                "import_job_id": str(job.id),
                "items_created": items_created,
                "status": job.status,
            })

        except Exception:
            logger.exception("Error parsing import source for job %s", import_job_id)
            job.status = "failed"
            self.database.db.commit()
            raise

    def _parse_url_list(self, job: ImportJob) -> int:
        """Handle URL list imports.

        Items are already pre-created by StartImport, so just return the count.
        """
        # URL list items are already created by StartImport with source_type="url"
        # and source_url set. total_items is already set by StartImport.
        return job.total_items

    def _parse_single_url(self, job: ImportJob) -> int:
        """Create a single ImportItem for a single URL import."""
        # Get URL from source_filename (used to store the URL for single imports)
        url = job.source_filename
        if not url:
            return 0

        item = ImportItem(
            import_job_id=job.id,
            source_type="url",
            source_url=url,
            status="pending",
        )
        self.database.create(item)
        return 1

    def _dispatch_extraction_tasks(self, job: ImportJob):
        """Dispatch ExtractRecipeTask for all pending items."""
        from utils.tasks.import_tasks.extract_recipe_task import extract_task

        # Get all pending item IDs
        items = self.database.db.query(ImportItem).filter(
            ImportItem.import_job_id == job.id,
            ImportItem.status == "pending"
        ).all()

        if not items:
            return

        # Dispatch in batches
        batch_size = 10
        item_ids = [str(item.id) for item in items]

        for i in range(0, len(item_ids), batch_size):
            batch = item_ids[i:i + batch_size]
            extract_task.delay(
                item_ids=batch,
                user_id=str(job.user_id),
            )


# Register task with Celery
parse_source_task = celery_app.register_task(ParseSourceTask())
