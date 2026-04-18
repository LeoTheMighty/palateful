"""Tests for source-photo promotion helper (bugs-imp-pho-3)."""

import uuid
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from utils.services.recipe_image_promotion import (
    _extract_extension,
    promote_source_photo,
)


def _make_aws_mock() -> MagicMock:
    """AWSService mock with a no-op copy_object by default."""
    aws = MagicMock()
    aws.copy_object = MagicMock(return_value=None)
    return aws


# ---------- _extract_extension ----------


def test_extract_extension_common_image():
    assert _extract_extension("uploads/abc.jpg") == "jpg"
    assert _extract_extension("uploads/abc.PNG") == "png"
    assert _extract_extension("uploads/abc.jpeg") == "jpeg"


def test_extract_extension_no_extension_defaults_to_jpg():
    assert _extract_extension("uploads/abc") == "jpg"


def test_extract_extension_trailing_dot_defaults_to_jpg():
    assert _extract_extension("uploads/abc.") == "jpg"


def test_extract_extension_dotted_folder_name():
    # Dots in folder segments must not be interpreted as extensions.
    assert _extract_extension("folder.name/abc.png") == "png"
    assert _extract_extension("folder.name/abc") == "jpg"


# ---------- promote_source_photo happy path ----------


def test_promote_source_photo_happy_path():
    aws = _make_aws_mock()
    user_id = uuid.uuid4()
    recipe_id = uuid.uuid4()

    url = promote_source_photo(
        aws,
        user_id=user_id,
        recipe_id=recipe_id,
        source_s3_key="uploads/user/photo.jpg",
        region="us-east-1",
        bucket="palateful-parser-inputs-prod",
    )

    assert url is not None
    assert url.startswith(
        "https://palateful-parser-inputs-prod.s3.us-east-1.amazonaws.com/"
    )
    # Dest key has the right shape + extension.
    call = aws.copy_object.call_args
    dest_key = call.kwargs["dest_key"]
    assert dest_key.startswith(f"recipe-photos/{user_id}/{recipe_id}/source-")
    assert dest_key.endswith(".jpg")
    assert call.kwargs["source_key"] == "uploads/user/photo.jpg"


def test_promote_source_photo_url_contains_dest_key():
    """The URL returned must embed the same dest key we asked S3 to copy to."""
    aws = _make_aws_mock()
    url = promote_source_photo(
        aws,
        user_id="u1",
        recipe_id="r1",
        source_s3_key="uploads/a.PNG",
        region="us-west-2",
        bucket="my-bucket",
    )
    dest_key = aws.copy_object.call_args.kwargs["dest_key"]
    assert url == f"https://my-bucket.s3.us-west-2.amazonaws.com/{dest_key}"
    # Extension is lowercased from PNG → png
    assert dest_key.endswith(".png")


# ---------- failure modes ----------


def test_promote_source_photo_client_error_returns_none():
    aws = _make_aws_mock()
    aws.copy_object.side_effect = ClientError(
        error_response={"Error": {"Code": "AccessDenied", "Message": "nope"}},
        operation_name="CopyObject",
    )

    url = promote_source_photo(
        aws,
        user_id="u1",
        recipe_id="r1",
        source_s3_key="uploads/a.jpg",
        region="us-east-1",
        bucket="bkt",
    )
    assert url is None


def test_promote_source_photo_unexpected_error_returns_none():
    aws = _make_aws_mock()
    aws.copy_object.side_effect = RuntimeError("network fell over")

    url = promote_source_photo(
        aws,
        user_id="u1",
        recipe_id="r1",
        source_s3_key="uploads/a.jpg",
        region="us-east-1",
        bucket="bkt",
    )
    assert url is None


def test_promote_source_photo_no_extension_uses_jpg():
    aws = _make_aws_mock()
    promote_source_photo(
        aws,
        user_id="u1",
        recipe_id="r1",
        source_s3_key="uploads/no-extension-key",
        region="us-east-1",
        bucket="bkt",
    )
    dest_key = aws.copy_object.call_args.kwargs["dest_key"]
    assert dest_key.endswith(".jpg")


# ---------- AWSService.copy_object defaults ----------


def test_aws_service_copy_object_defaults_to_parser_inputs_bucket():
    """copy_object should default both source+dest buckets to parser_inputs
    so same-bucket promotion needs no overrides."""
    from utils.services.aws import AWSService

    svc = AWSService.__new__(AWSService)  # bypass __init__ (no boto3 client)
    svc.parser_inputs_bucket = "palateful-parser-inputs-dev"
    svc.parser_outputs_bucket = "out"
    fake_s3 = MagicMock()
    svc._s3 = fake_s3

    svc.copy_object(source_key="uploads/a.jpg", dest_key="recipe-photos/b.jpg")

    fake_s3.copy_object.assert_called_once_with(
        Bucket="palateful-parser-inputs-dev",
        Key="recipe-photos/b.jpg",
        CopySource={"Bucket": "palateful-parser-inputs-dev", "Key": "uploads/a.jpg"},
    )


def test_aws_service_copy_object_cross_bucket_override():
    from utils.services.aws import AWSService

    svc = AWSService.__new__(AWSService)
    svc.parser_inputs_bucket = "pin"
    svc.parser_outputs_bucket = "pout"
    fake_s3 = MagicMock()
    svc._s3 = fake_s3

    svc.copy_object(
        source_key="uploads/a.jpg",
        dest_key="recipe-photos/b.jpg",
        source_bucket="src-override",
        dest_bucket="dst-override",
    )

    fake_s3.copy_object.assert_called_once_with(
        Bucket="dst-override",
        Key="recipe-photos/b.jpg",
        CopySource={"Bucket": "src-override", "Key": "uploads/a.jpg"},
    )
