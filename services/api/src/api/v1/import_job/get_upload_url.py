"""Presigned upload URL endpoint for file-based imports."""

import uuid
from datetime import UTC, datetime, timedelta

from config import settings
from pydantic import BaseModel, Field
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.services.aws import AWSService

# 100 MiB. Cross-epic-locked: the iOS Share Extension and the Flutter
# receive screen surface a hard-stop above this; the presigned URL also
# signs the exact byte count so a malicious client can't reuse the URL
# for a larger payload.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024

# Canonical mime → extension. The extension lands in the s3_key, so it
# has to be deterministic per mime — we don't trust user-supplied
# filenames in the key (collision + injection risk per epic).
_MIME_EXT: dict[str, str] = {
    "application/pdf": "pdf",
    # image/*
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
    # audio/*
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/aac": "aac",
    "audio/ogg": "ogg",
    "audio/webm": "weba",
    # video/*
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/x-m4v": "m4v",
    "video/webm": "webm",
    # spreadsheets / text
    "text/csv": "csv",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/plain": "txt",
}


_aws_service: AWSService | None = None


def _get_aws_service() -> AWSService:  # pragma: no cover — singleton init, mocked
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


class GetImportUploadUrl(AsyncEndpoint):
    """Generate a presigned S3 PUT URL for uploading a file-based import."""

    async def execute(self, params: "GetImportUploadUrl.Params"):
        # Size validation — explicit error codes, not Pydantic 422.
        # ifh-1: every malformed-input failure here is permanent. The
        # client's only recovery is to either pick a different file or
        # surface to the user — re-POSTing the same payload will fail
        # the same way every time.
        if params.size_bytes <= 0:
            raise APIException(
                status_code=400,
                detail="size_bytes must be greater than 0",
                code=ErrorCode.INVALID_REQUEST,
                retryable=False,
            )
        if params.size_bytes > MAX_UPLOAD_BYTES:
            raise APIException(
                status_code=413,
                detail=(
                    f"File too large — max {MAX_UPLOAD_BYTES} bytes "
                    f"(received {params.size_bytes})"
                ),
                code=ErrorCode.FILE_TOO_LARGE,
                retryable=False,
            )

        ext = _MIME_EXT.get(params.mime_type)
        if ext is None:
            raise APIException(
                status_code=400,
                detail=f"Unsupported mime type: {params.mime_type}",
                code=ErrorCode.UNSUPPORTED_MIME,
                retryable=False,
            )

        # imports/{user_id}/{object_uuid}.{ext} — ownership is encoded in
        # the prefix; sbf-3 enforces it on the matching /import call.
        object_uuid = str(uuid.uuid4())
        s3_key = f"imports/{self.user.id}/{object_uuid}.{ext}"

        upload_url, required_headers = await _get_aws_service().presign_put_url_async(
            s3_key=s3_key,
            bucket=settings.s3_imports_bucket,
            content_type=params.mime_type,
            content_length=params.size_bytes,
            tagging="unclaimed=true",
            expires_in=3600,
        )

        expires_at = datetime.now(UTC) + timedelta(seconds=3600)

        return success(
            data=GetImportUploadUrl.Response(
                upload_url=upload_url,
                s3_key=s3_key,
                required_headers=required_headers,
                expires_at=expires_at,
            )
        )

    class Params(BaseModel):
        filename: str = Field(min_length=1, max_length=255)
        mime_type: str = Field(min_length=1, max_length=128)
        size_bytes: int

    class Response(BaseModel):
        upload_url: str
        s3_key: str
        required_headers: dict[str, str]
        expires_at: datetime
