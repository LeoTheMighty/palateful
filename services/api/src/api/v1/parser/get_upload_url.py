"""Get presigned upload URL endpoint."""

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from config import settings
from utils.api.endpoint import Endpoint, success
from utils.services.aws import AWSService


class GetUploadUrl(Endpoint):
    """Generate a presigned S3 URL for uploading an image."""

    def execute(self, params: "GetUploadUrl.Params"):
        """
        Generate a presigned URL for uploading an image to S3.

        Args:
            params: Request parameters with filename.

        Returns:
            Presigned upload URL and S3 key.
        """
        # Generate unique S3 key
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        extension = params.filename.split(".")[-1] if "." in params.filename else "jpg"
        s3_key = f"uploads/{self.user.id}/{timestamp}_{unique_id}.{extension}"

        # Determine content type
        content_type_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "heic": "image/heic",
            "heif": "image/heif",
        }
        content_type = content_type_map.get(extension.lower(), "image/jpeg")

        # Generate presigned URL
        aws = AWSService(
            region=settings.aws_region,
            parser_inputs_bucket=settings.parser_inputs_bucket,
            parser_outputs_bucket=settings.parser_outputs_bucket,
            batch_job_queue=settings.batch_job_queue,
            batch_job_definition=settings.batch_job_definition,
        )

        upload_url = aws.generate_presigned_upload_url(
            s3_key=s3_key,
            content_type=content_type,
            expires_in=3600,  # 1 hour
        )

        return success(
            data=GetUploadUrl.Response(
                upload_url=upload_url,
                s3_key=s3_key,
                content_type=content_type,
            )
        )

    class Params(BaseModel):
        filename: str

    class Response(BaseModel):
        upload_url: str
        s3_key: str
        content_type: str
