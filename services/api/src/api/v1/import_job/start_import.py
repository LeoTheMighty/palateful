"""Start import endpoint."""

import logging
import time
from datetime import datetime

from botocore.exceptions import ClientError
from config import settings
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from utils.api.endpoint import APIException, Endpoint, failure, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.services.aws import AWSService
from utils.services.url_classifier import SocialPlatform, detect_platform
from utils.tasks.import_tasks.parse_source_task import parse_source_task

logger = logging.getLogger(__name__)

# Per-user rate limit for /import (sbf-3). In-memory sliding window;
# applies to both s3_key and file_base64 paths so a base64 storm can't
# bypass the cap. Acceptable for 2-instance ECS (worst case 60/hr/user).
_RATE_LIMIT_MAX = 30
_RATE_LIMIT_WINDOW_S = 3600
_rate_limit_events: dict[str, list[float]] = {}


def _check_rate_limit(user_id: str) -> tuple[bool, int]:
    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW_S
    times = _rate_limit_events.setdefault(user_id, [])
    times[:] = [t for t in times if t > cutoff]
    if len(times) >= _RATE_LIMIT_MAX:
        retry_after = int(times[0] + _RATE_LIMIT_WINDOW_S - now) + 1
        return False, max(retry_after, 1)
    times.append(now)
    return True, 0


def _reset_rate_limit_for_test() -> None:
    _rate_limit_events.clear()


_S3_KEY_SOURCE_TYPES = {"audio", "pdf", "spreadsheet", "video_file"}

_aws_service: AWSService | None = None


def _get_aws_service() -> AWSService:  # pragma: no cover — singleton, mocked
    global _aws_service
    if _aws_service is None:
        _aws_service = AWSService(
            region=settings.aws_region,
            parser_inputs_bucket=settings.parser_inputs_bucket,
            parser_outputs_bucket=settings.parser_outputs_bucket,
            batch_job_queue=settings.batch_job_queue,
            batch_job_definition=settings.batch_job_definition,
        )
    return _aws_service


class StartImport(Endpoint):
    """Start a new recipe import job."""

    def execute(self, book_id: str, params: "StartImport.Params"):
        """
        Start a new import job for the recipe book.

        Args:
            book_id: The recipe book ID to import into.
            params: Import parameters including source type and URLs.

        Returns:
            Created import job data.
        """
        user: User = self.user

        # Idempotency short-circuit. The iOS Share Extension POSTs once
        # on save, and the Flutter reconciler re-POSTs the same record
        # on every app resume until the extension's URLSession callback
        # clears it. Without this check, a single share produced
        # duplicate ImportJobs. Runs before rate-limit so a legit
        # reconciler retry doesn't burn a rate slot.
        if params.idempotency_key:
            existing_job = self._find_existing_job(
                user_id=str(user.id),
                idempotency_key=params.idempotency_key,
            )
            if existing_job is not None:
                return success(
                    data=StartImport.Response(
                        id=str(existing_job.id),
                        status=existing_job.status,
                        source_type=existing_job.source_type,
                        total_items=existing_job.total_items,
                        recipe_book_id=str(existing_job.recipe_book_id),
                        created_at=existing_job.created_at,
                    ),
                    status=200,
                )

        # sbf-3: per-user rate limit first; over-cap doesn't consume state.
        allowed, retry_after = _check_rate_limit(str(user.id))
        if not allowed:
            logger.info(
                "import: user=%s rate-limited retry_after_s=%d",
                user.id, retry_after,
            )
            return failure(
                status=429,
                error_code=ErrorCode.RATE_LIMITED.value,
                error_message=(
                    f"Too many imports (max {_RATE_LIMIT_MAX}/hour). "
                    f"Retry in {retry_after}s."
                ),
                retry_after=retry_after,
            )

        # sbf-3: mutual exclusion between s3_key and file_base64 paths.
        if params.s3_key and params.file_base64:
            raise APIException(
                status_code=400,
                detail="s3_key and file_base64 are mutually exclusive",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Check access - must be owner or editor
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=book_id,
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to import recipes to this book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        # Verify recipe book exists
        recipe_book = self.database.find_by(RecipeBook, id=book_id)
        if not recipe_book:
            raise APIException(
                status_code=404,
                detail=f"Recipe book with ID '{book_id}' not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND,
            )

        # Validate input based on source type
        if params.source_type == "url":
            if not params.url:
                raise APIException(
                    status_code=400,
                    detail="URL is required for url source type",
                    code=ErrorCode.INVALID_REQUEST,
                )
            source_filename = params.url
        elif params.source_type == "url_list":
            if not params.urls or len(params.urls) == 0:
                raise APIException(
                    status_code=400,
                    detail="URLs are required for url_list source type",
                    code=ErrorCode.INVALID_REQUEST,
                )
            source_filename = None
        elif params.source_type == "photo":
            if not params.ocr_texts or len(params.ocr_texts) == 0:
                raise APIException(
                    status_code=400,
                    detail="OCR texts are required for photo source type",
                    code=ErrorCode.INVALID_REQUEST,
                )
            source_filename = "photo_import"
        elif params.source_type == "text":
            if not params.raw_text or len(params.raw_text.strip()) == 0:
                raise APIException(
                    status_code=400,
                    detail="raw_text is required for text source type",
                    code=ErrorCode.INVALID_REQUEST,
                )
            if len(params.raw_text) > 16000:
                raise APIException(
                    status_code=400,
                    detail="Text too long — maximum 16,000 characters",
                    code=ErrorCode.INVALID_REQUEST,
                )
            source_filename = "text_paste"
        elif params.source_type == "audio":
            if params.s3_key:
                self._validate_s3_key_inputs(params, user)
                source_filename = params.file_name or params.s3_key
            elif not params.file_base64 or not params.file_name:
                raise APIException(
                    status_code=400,
                    detail="file_base64 and file_name (or s3_key) are required for audio import",
                    code=ErrorCode.INVALID_REQUEST,
                )
            else:
                source_filename = params.file_name
        elif params.source_type == "pdf":
            if params.s3_key:
                self._validate_s3_key_inputs(params, user)
                source_filename = params.file_name or params.s3_key
            elif not params.file_base64 or not params.file_name:
                raise APIException(
                    status_code=400,
                    detail="file_base64 and file_name (or s3_key) are required for PDF import",
                    code=ErrorCode.INVALID_REQUEST,
                )
            else:
                source_filename = params.file_name
        elif params.source_type == "spreadsheet":
            if params.s3_key:
                self._validate_s3_key_inputs(params, user)
                source_filename = params.file_name or params.s3_key
            elif not params.file_base64 or not params.file_name:
                raise APIException(
                    status_code=400,
                    detail="file_base64 and file_name (or s3_key) are required for spreadsheet import",
                    code=ErrorCode.INVALID_REQUEST,
                )
            else:
                source_filename = params.file_name
        elif params.source_type == "video_file":
            # sbf-4: video_file is s3_key-only. Presigned PUT is the only
            # way a client sends a 100 MB clip to the backend.
            if not params.s3_key:
                raise APIException(
                    status_code=400,
                    detail="s3_key is required for video_file import",
                    code=ErrorCode.INVALID_REQUEST,
                )
            self._validate_s3_key_inputs(params, user)
            source_filename = params.file_name or params.s3_key
        else:
            raise APIException(
                status_code=400,
                detail=f"Unsupported source type: {params.source_type}",
                code=ErrorCode.IMPORT_INVALID_SOURCE_TYPE,
            )

        # Create import job
        job = ImportJob(
            status="pending",
            source_type=params.source_type,
            source_filename=source_filename,
            user_id=user.id,
            recipe_book_id=book_id,
            idempotency_key=params.idempotency_key,
        )
        try:
            self.database.create(job)
        except IntegrityError:
            # Only the (user_id, idempotency_key) partial UNIQUE can
            # fire here — so if there's no key, we have nothing to
            # recover and must surface. If a key was supplied this is a
            # true race: the pre-check above missed a concurrent
            # /import that already persisted. Return the winner so both
            # callers see the same job.
            if params.idempotency_key is None:
                raise
            winner = self._find_existing_job(
                user_id=str(user.id),
                idempotency_key=params.idempotency_key,
            )
            return success(
                data=StartImport.Response(
                    id=str(winner.id),
                    status=winner.status,
                    source_type=winner.source_type,
                    total_items=winner.total_items,
                    recipe_book_id=str(winner.recipe_book_id),
                    created_at=winner.created_at,
                ),
                status=200,
            )
        self.database.db.refresh(job)

        # Create import items for URL list
        if params.source_type == "url_list" and params.urls:
            for idx, url in enumerate(params.urls):
                item = ImportItem(
                    import_job_id=job.id,
                    source_type="url",
                    source_reference=str(idx + 1),
                    source_url=url,
                    status="pending",
                )
                self.database.create(item)
            job.total_items = len(params.urls)
            self.database.db.commit()
        elif params.source_type == "url":
            # sbf-5: social URL routing moved upstream. extract_recipe_task
            # still has a defensive check, but the primary decision is
            # here so Activity Hub can label rows correctly (e.g.
            # "Importing from TikTok video") from the moment the item
            # exists.
            platform = detect_platform(params.url or "")
            item_source_type = (
                "video" if platform != SocialPlatform.WEB else "url"
            )
            item_raw_data: dict = {}
            if platform != SocialPlatform.WEB:
                item_raw_data["detected_platform"] = platform.value
            item = ImportItem(
                import_job_id=job.id,
                source_type=item_source_type,
                source_url=params.url,
                raw_data=item_raw_data,
                status="pending",
            )
            self.database.create(item)
            job.total_items = 1
            self.database.db.commit()
        elif params.source_type == "photo" and params.ocr_texts:  # pragma: no cover — validated above
            # Concatenate all OCR texts into a single import item
            combined_text = "\n\n---\n\n".join(params.ocr_texts)
            item = ImportItem(
                import_job_id=job.id,
                source_type="photo",
                raw_data={"text": combined_text},
                status="pending",
            )
            self.database.create(item)
            job.total_items = 1
            self.database.db.commit()
        elif params.source_type == "text" and params.raw_text:
            item = ImportItem(
                import_job_id=job.id,
                source_type="text",
                raw_data={"text": params.raw_text.strip()},
                status="pending",
            )
            self.database.create(item)
            job.total_items = 1
            self.database.db.commit()
        elif params.source_type == "audio" and params.file_base64:  # pragma: no branch
            import base64
            import tempfile

            from utils.services.recipe_extractors.audio_extractor import (
                transcribe_audio,
            )

            file_bytes = base64.b64decode(params.file_base64)

            # Write to temp file for transcription
            with tempfile.NamedTemporaryFile(suffix=f".{(params.file_name or 'audio.m4a').split('.')[-1]}", delete=False) as f:
                f.write(file_bytes)
                audio_path = f.name

            try:
                transcript, cost_cents = transcribe_audio(audio_path)
            finally:
                import os
                os.unlink(audio_path)

            item = ImportItem(
                import_job_id=job.id,
                source_type="text",
                raw_data={"text": transcript, "is_audio_import": True, "transcription_cost_cents": cost_cents},
                status="pending",
                ai_cost_cents=cost_cents,
            )
            self.database.create(item)
            job.total_items = 1
            job.total_ai_cost_cents = cost_cents
            self.database.db.commit()
        elif params.source_type == "pdf" and params.file_base64:  # pragma: no branch
            import base64

            from utils.services.recipe_extractors.pdf_extractor import (
                classify_pdf,
                detect_recipe_boundaries,
                extract_text_from_pdf,
            )

            file_bytes = base64.b64decode(params.file_base64)
            pdf_type, page_count = classify_pdf(file_bytes)

            if pdf_type.value == "text":
                text = extract_text_from_pdf(file_bytes)
                recipes = detect_recipe_boundaries(text)
                for i, recipe_chunk in enumerate(recipes):
                    item = ImportItem(
                        import_job_id=job.id,
                        source_type="text",
                        source_reference=f"recipe_{i + 1}",
                        raw_data={"text": recipe_chunk["text"], "pdf_recipe_title": recipe_chunk.get("title")},
                        status="pending",
                    )
                    self.database.create(item)
                job.total_items = len(recipes)
            else:
                # Scanned PDF — treat each page as a separate item
                item = ImportItem(
                    import_job_id=job.id,
                    source_type="text",
                    raw_data={"text": extract_text_from_pdf(file_bytes), "is_scanned_pdf": True},
                    status="pending",
                )
                self.database.create(item)
                job.total_items = 1
            self.database.db.commit()
        elif params.source_type == "spreadsheet" and params.file_base64:
            import base64

            from utils.services.spreadsheet_parser import parse_spreadsheet

            file_bytes = base64.b64decode(params.file_base64)
            rows = parse_spreadsheet(file_bytes, params.file_name or "file.csv")
            for row_text in rows:
                item = ImportItem(
                    import_job_id=job.id,
                    source_type="text",
                    raw_data={"text": row_text},
                    status="pending",
                )
                self.database.create(item)
            job.total_items = len(rows)
            self.database.db.commit()
        elif (  # pragma: no branch  # upstream validation ensures one arm of the elif chain always matches
            params.source_type in _S3_KEY_SOURCE_TYPES
            and params.s3_key
        ):
            # sbf-3: s3_key branch — parse bytes in the worker, not here.
            # The item carries the s3_key on the dedicated column (replay
            # guard via partial UNIQUE index); `raw_data` preserves the
            # upload metadata so debugging and the worker's S3 fetch have
            # everything they need.
            try:
                item = ImportItem(
                    import_job_id=job.id,
                    source_type=params.source_type,
                    s3_key=params.s3_key,
                    raw_data={
                        "s3_key": params.s3_key,
                        "original_filename": params.file_name,
                        "mime_type": params.mime_type,
                        "etag": params.etag,
                    },
                    status="pending",
                )
                self.database.create(item)
                job.total_items = 1
                self.database.db.commit()
            except IntegrityError:
                # Concurrent /import for the same key raced past the
                # in-endpoint dedupe query; the partial UNIQUE index is
                # the second line of defense. Roll back the open job +
                # activity row so we don't leak half-created state.
                self.database.db.rollback()
                return failure(
                    status=409,
                    error_code=ErrorCode.DUPLICATE_IMPORT.value,
                    error_message="This file has already been imported.",
                )

        # abi-2a: no longer writes an `import_started` user_activity
        # row. The Imports tab reads `import_items` directly, and push
        # dispatch for imports reads import_item state — the parallel
        # user_activity write only existed to drive a bell count that
        # the Notifications-tab allow-list (abi-1) now excludes.

        # Dispatch background processing
        parse_source_task.delay(
            import_job_id=str(job.id),
            user_id=str(user.id),
        )

        return success(
            data=StartImport.Response(
                id=str(job.id),
                status=job.status,
                source_type=job.source_type,
                total_items=job.total_items,
                recipe_book_id=str(job.recipe_book_id),
                created_at=job.created_at,
            ),
            status=201,
        )

    def _find_existing_job(
        self,
        user_id: str,
        idempotency_key: str,
    ) -> ImportJob | None:
        return (
            self.database.db.query(ImportJob)
            .filter(
                ImportJob.user_id == user_id,
                ImportJob.idempotency_key == idempotency_key,
            )
            .first()
        )

    def _validate_s3_key_inputs(self, params: "StartImport.Params", user: User) -> None:
        """sbf-3: validate s3_key ownership + object readiness + replay.

        Runs in this order so the cheapest/clearest failures surface
        first: prefix check → HeadObject → in-endpoint dedupe query.
        The DB UNIQUE index (see migration 20260418070000) is the second
        line of defense if a concurrent /import call races past this
        check — that path is handled by the IntegrityError branch in
        the s3_key ImportItem creation block.
        """
        s3_key = params.s3_key or ""
        expected_prefix = f"imports/{user.id}/"
        if not s3_key.startswith(expected_prefix):
            raise APIException(
                status_code=403,
                detail="s3_key does not belong to the current user",
                code=ErrorCode.CROSS_USER_KEY,
            )

        aws = _get_aws_service()
        bucket = settings.s3_imports_bucket
        try:
            aws.head_object(s3_key, bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise APIException(
                    status_code=409,
                    detail="Upload is not yet visible in S3. Retry shortly.",
                    code=ErrorCode.OBJECT_NOT_READY,
                ) from exc
            raise

        existing = self.database.db.query(ImportItem).filter(
            ImportItem.s3_key == s3_key,
        ).first()
        if existing is not None:
            raise APIException(
                status_code=409,
                detail="This file has already been imported.",
                code=ErrorCode.DUPLICATE_IMPORT,
            )

    class Params(BaseModel):
        source_type: str
        urls: list[str] | None = Field(default=None, max_length=50)
        url: str | None = None
        ocr_texts: list[str] | None = Field(default=None, max_length=10)
        raw_text: str | None = None
        file_base64: str | None = None
        file_name: str | None = None
        # sbf-3: presigned-upload path. When set, the endpoint skips
        # base64 decoding and instead verifies S3 ownership + object
        # readiness, then the worker reads bytes from S3.
        s3_key: str | None = None
        etag: str | None = None
        mime_type: str | None = None
        # Replay token supplied by the iOS Share Extension and the Flutter
        # reconciler so a double-fire returns the existing job instead of
        # creating a duplicate. Scoped per-user by the partial UNIQUE
        # index on import_jobs.
        idempotency_key: str | None = Field(default=None, max_length=128)

    class Response(BaseModel):
        id: str
        status: str
        source_type: str
        total_items: int
        recipe_book_id: str
        created_at: datetime
