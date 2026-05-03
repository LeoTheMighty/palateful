"""Parse source task - parses import source and creates ImportItem records."""

import contextlib
import logging
import os
import tempfile
from datetime import UTC, datetime

from utils import constants
from utils.api.endpoint import success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.services.aws import AWSService
from utils.services.celery import celery_app
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

_S3_KEYED_SOURCE_TYPES = ("audio", "pdf", "spreadsheet", "video_file")


class ParseSourceTask(BaseTask):
    """Parse import source and create ImportItem records.

    This task handles the initial parsing of import sources:
    - url_list: Creates one ImportItem per URL
    - spreadsheet: Parses CSV/Excel and creates items per row (future)
    - pdf: Detects recipe boundaries and creates items (future)
    """

    name = "parse_source_task"

    def _aws_service(self) -> AWSService:  # pragma: no cover - mocked in tests
        return AWSService(region=constants.AWS_REGION)

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
            elif (
                job.source_type in _S3_KEYED_SOURCE_TYPES
                and self._has_s3_keyed_items(job)
            ):
                # sbf-3: presigned-upload path. StartImport created one
                # item with `s3_key` set; we fetch bytes here and fan out
                # into text items for multi-recipe PDFs / multi-row
                # spreadsheets so the existing extractor pipeline runs
                # unchanged.
                items_created = self._parse_s3_keyed_files(job)
            elif job.source_type in ("photo", "text", "spreadsheet", "audio", "pdf", "video_file", "image"):
                # Items are already created by StartImport with text in raw_data.
                # total_items is already set by StartImport, so just read the count.
                # share-img-1: `image` is intentionally a no-op at the parse
                # stage — vision extraction is a single round-trip and runs
                # in `extract_recipe_task` directly off the s3_key, so there
                # is nothing to decode here.
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

    def _has_s3_keyed_items(self, job: ImportJob) -> bool:
        items = self.database.db.query(ImportItem).filter(
            ImportItem.import_job_id == job.id,
        ).all()
        return any(item.s3_key is not None for item in items)

    def _parse_s3_keyed_files(self, job: ImportJob) -> int:
        """sbf-3: fetch bytes from S3 and parse per source_type.

        The first item on the job is the one StartImport created with
        `s3_key` populated. For audio we rewrite that single item into a
        text item carrying the transcript. For PDFs we fan out: the
        first recipe overwrites the original item, subsequent recipes
        become sibling items. Spreadsheets behave the same way per row.
        """
        items = self.database.db.query(ImportItem).filter(
            ImportItem.import_job_id == job.id,
        ).all()
        seed = next((i for i in items if i.s3_key), None)
        if seed is None:
            return 0

        bucket = constants.S3_IMPORTS_BUCKET
        aws = self._aws_service()
        file_bytes = aws.read_object(seed.s3_key, bucket)

        source_type = job.source_type
        if source_type == "audio":
            return self._parse_audio_bytes(job, seed, file_bytes)
        if source_type == "pdf":
            return self._parse_pdf_bytes(job, seed, file_bytes)
        if source_type == "spreadsheet":
            return self._parse_spreadsheet_bytes(job, seed, file_bytes)
        if source_type == "video_file":
            return self._parse_video_file(job, seed, file_bytes)
        return 0  # pragma: no cover — guarded by caller

    def _parse_audio_bytes(
        self, job: ImportJob, item: ImportItem, file_bytes: bytes,
    ) -> int:
        from utils.services.recipe_extractors.audio_extractor import (
            transcribe_audio,
        )

        original_name = (item.raw_data or {}).get("original_filename") or "audio.m4a"
        suffix = f".{original_name.split('.')[-1]}" if "." in original_name else ".m4a"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fh:
            fh.write(file_bytes)
            audio_path = fh.name
        try:
            transcript, cost_cents = transcribe_audio(audio_path)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(audio_path)

        item.source_type = "text"
        item.raw_data = {
            **(item.raw_data or {}),
            "text": transcript,
            "is_audio_import": True,
            "transcription_cost_cents": cost_cents,
        }
        item.ai_cost_cents = (item.ai_cost_cents or 0) + cost_cents
        job.total_ai_cost_cents = (job.total_ai_cost_cents or 0) + cost_cents
        self.database.db.commit()
        return 1

    def _parse_pdf_bytes(
        self, job: ImportJob, item: ImportItem, file_bytes: bytes,
    ) -> int:
        from utils.services.recipe_extractors.pdf_extractor import (
            classify_pdf,
            detect_recipe_boundaries,
            extract_text_from_pdf,
        )

        pdf_type, _page_count = classify_pdf(file_bytes)
        text = extract_text_from_pdf(file_bytes)

        if pdf_type.value == "text":
            recipes = detect_recipe_boundaries(text)
            if not recipes:
                recipes = [{"text": text, "title": None}]
            first = recipes[0]
            item.source_type = "text"
            item.raw_data = {
                **(item.raw_data or {}),
                "text": first["text"],
                "pdf_recipe_title": first.get("title"),
            }
            for i, chunk in enumerate(recipes[1:], start=2):
                sibling = ImportItem(
                    import_job_id=job.id,
                    source_type="text",
                    source_reference=f"recipe_{i}",
                    raw_data={
                        "text": chunk["text"],
                        "pdf_recipe_title": chunk.get("title"),
                    },
                    status="pending",
                )
                self.database.create(sibling)
            self.database.db.commit()
            return len(recipes)

        # Scanned PDF — one item carrying the full OCR body.
        item.source_type = "text"
        item.raw_data = {
            **(item.raw_data or {}),
            "text": text,
            "is_scanned_pdf": True,
        }
        self.database.db.commit()
        return 1

    def _parse_video_file(
        self, job: ImportJob, item: ImportItem, file_bytes: bytes,
    ) -> int:
        """sbf-4: ffmpeg → audio track → Whisper → text rewrite.

        video_file imports collapse to the same final shape as the audio
        path (one text item with the transcript). The only extra step is
        the ffmpeg decode, which is isolated to its own process group so
        a Celery soft-time-limit signals the whole tree.
        """
        from utils.classes.error_code import ErrorCode
        from utils.services.recipe_extractors.audio_extractor import (
            transcribe_audio,
        )
        from utils.services.recipe_extractors.video_file_extractor import (
            VideoDecodeError,
            extract_audio_to_file,
        )

        with tempfile.NamedTemporaryFile(suffix=".video", delete=False) as in_fh:
            in_fh.write(file_bytes)
            video_path = in_fh.name
        out_fd, audio_path = tempfile.mkstemp(suffix=".mp3")
        os.close(out_fd)

        try:
            try:
                extract_audio_to_file(video_path, audio_path)
            except VideoDecodeError as exc:
                item.status = "failed"
                item.error_code = "video_decode_failed"
                item.error_message = f"ffmpeg failed: {exc.stderr_tail[-500:]}"
                item.raw_data = {
                    **(item.raw_data or {}),
                    "ffmpeg_stderr_tail": exc.stderr_tail[-500:],
                }
                self.database.db.commit()
                job.status = "failed"
                self.database.db.commit()
                logger.warning(
                    "video_file ffmpeg failed job=%s item=%s code=%s",
                    job.id, item.id, ErrorCode.IMPORT_EXTRACTION_FAILED.value,
                )
                return 1

            transcript, cost_cents = transcribe_audio(audio_path)
        finally:
            for path in (video_path, audio_path):
                with contextlib.suppress(OSError):
                    os.unlink(path)

        item.source_type = "text"
        item.raw_data = {
            **(item.raw_data or {}),
            "text": transcript,
            "is_audio_import": True,
            "is_video_file_import": True,
            "transcription_cost_cents": cost_cents,
        }
        item.ai_cost_cents = (item.ai_cost_cents or 0) + cost_cents
        job.total_ai_cost_cents = (job.total_ai_cost_cents or 0) + cost_cents
        self.database.db.commit()
        return 1

    def _parse_spreadsheet_bytes(
        self, job: ImportJob, item: ImportItem, file_bytes: bytes,
    ) -> int:
        from utils.services.spreadsheet_parser import parse_spreadsheet

        filename = (item.raw_data or {}).get("original_filename") or "file.csv"
        rows = parse_spreadsheet(file_bytes, filename)
        if not rows:
            item.source_type = "text"
            item.raw_data = {**(item.raw_data or {}), "text": ""}
            self.database.db.commit()
            return 1

        item.source_type = "text"
        item.raw_data = {**(item.raw_data or {}), "text": rows[0]}
        for row_text in rows[1:]:
            sibling = ImportItem(
                import_job_id=job.id,
                source_type="text",
                raw_data={"text": row_text},
                status="pending",
            )
            self.database.create(sibling)
        self.database.db.commit()
        return len(rows)

    def _dispatch_extraction_tasks(self, job: ImportJob):
        """Dispatch ExtractRecipeTask for all pending items."""
        from utils.constants import STAGE_PARSED
        from utils.logging import log_stage_transition
        from utils.tasks.import_tasks.extract_recipe_task import extract_task

        # Get all pending item IDs
        items = self.database.db.query(ImportItem).filter(
            ImportItem.import_job_id == job.id,
            ImportItem.status == "pending"
        ).all()

        if not items:
            return

        # All pending items under this job have reached the "parsed" stage by
        # virtue of existing with raw_data; mark them so the retry endpoint can
        # resume from the next stage instead of starting over.
        for item in items:
            item.last_successful_stage = STAGE_PARSED
        self.database.db.commit()

        # Stage-transition audit (irrd-2): emit a "parsed/ok" row per item so
        # GetImportItemTelemetry can surface the timeline without re-deriving
        # from job shape. Preview = raw OCR/text payload when present (photo
        # imports); null for URL/spreadsheet imports where there is no
        # human-readable parser stage.
        for item in items:
            raw_preview = (item.raw_data or {}).get("text") or None
            log_stage_transition(
                import_item_id=item.id,
                stage=STAGE_PARSED,
                status="ok",
                raw_output_preview=raw_preview,
            )

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
