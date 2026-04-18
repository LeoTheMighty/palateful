"""Source-photo promotion helper (bugs-imp-pho-3 / FR87).

When a photo import → recipe has no extractor-supplied `image_url`,
`create_recipe_task` copies the user-uploaded source photo from the
parser-inputs bucket to a permanent recipe-photos/ key in the same
bucket and uses the resulting URL as the recipe's hero image.

This module is pure-ish: it only depends on `AWSService` and returns
`None` on any S3 failure so recipe creation never fails because the
hero-image fallback did.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from botocore.exceptions import ClientError

from utils.services.aws import AWSService

logger = logging.getLogger(__name__)


def _extract_extension(source_s3_key: str) -> str:
    """Return the lowercase extension of `source_s3_key`, defaulting to `jpg`.

    Accepts keys with no extension or with segments containing dots — we
    only look at the final path component.
    """
    tail = source_s3_key.rsplit("/", 1)[-1]
    if "." in tail and not tail.endswith("."):
        ext = tail.rsplit(".", 1)[-1].lower()
        return ext or "jpg"
    return "jpg"


def promote_source_photo(
    aws: AWSService,
    user_id: UUID | str,
    recipe_id: UUID | str,
    source_s3_key: str,
    region: str,
    bucket: str,
) -> str | None:
    """Copy a parser-input photo to a permanent recipe-photos/ location.

    Returns the public S3 URL on success. Returns `None` and logs at
    WARN level on any failure (recipe creation is not blocked by a bad
    copy — FR87 is a best-effort hero fallback).

    The dest key is deterministic-per-call but timestamped, so retries
    produce a fresh key rather than reusing a potentially-half-copied
    object.
    """
    try:
        ext = _extract_extension(source_s3_key)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        dest_key = f"recipe-photos/{user_id}/{recipe_id}/source-{timestamp}.{ext}"
        aws.copy_object(source_key=source_s3_key, dest_key=dest_key)
        return f"https://{bucket}.s3.{region}.amazonaws.com/{dest_key}"
    except ClientError:
        logger.warning(
            "promote_source_photo: S3 copy failed for key %s",
            source_s3_key,
            exc_info=True,
        )
        return None
    except Exception:
        logger.warning(
            "promote_source_photo: unexpected error for key %s",
            source_s3_key,
            exc_info=True,
        )
        return None
