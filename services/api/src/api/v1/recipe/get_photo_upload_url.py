"""Get presigned upload URL for recipe photo."""

import uuid
from datetime import UTC, datetime

from config import settings
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.services.aws import AWSService


_aws_service = None


def _get_aws_service():
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


class GetRecipePhotoUploadUrl(Endpoint):
    """Generate a presigned S3 URL for uploading a recipe hero photo."""

    def execute(self, recipe_id: str, params: "GetRecipePhotoUploadUrl.Params"):
        """
        Generate a presigned URL for uploading a recipe photo to S3.

        Args:
            recipe_id: The recipe's ID.
            params: Request parameters with filename.

        Returns:
            Presigned upload URL, S3 key, content type, and public URL.
        """
        # Verify recipe exists
        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail="Recipe not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        # Verify user has access to the recipe's book
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=str(self.user.id),
            recipe_book_id=recipe.recipe_book_id,
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to modify this recipe",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        # Generate unique S3 key
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        extension = params.filename.split(".")[-1] if "." in params.filename else "jpg"
        s3_key = f"recipe-photos/{self.user.id}/{recipe_id}/{timestamp}_{unique_id}.{extension}"

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

        upload_url = _get_aws_service().generate_presigned_upload_url(
            s3_key=s3_key,
            content_type=content_type,
            expires_in=3600,
        )

        # Construct the public URL for the uploaded image
        image_url = f"https://{settings.parser_inputs_bucket}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"

        return success(
            data=GetRecipePhotoUploadUrl.Response(
                upload_url=upload_url,
                s3_key=s3_key,
                content_type=content_type,
                image_url=image_url,
            )
        )

    class Params(BaseModel):
        filename: str

    class Response(BaseModel):
        upload_url: str
        s3_key: str
        content_type: str
        image_url: str
