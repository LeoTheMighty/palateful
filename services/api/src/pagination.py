"""Opaque cursor encoding / decoding for paginated list endpoints.

afh-1a: multi-key cursor matching the See-all ORDER BY
``archived_at DESC NULLS LAST, created_at DESC, id DESC``.

Encoded format: ``base64url("{archived_at_ms|'-'}|{created_at_ms}|{row_id}")``.

- ``archived_at_ms`` is the Unix timestamp in milliseconds, or the literal
  ``-`` sentinel for NULL (maps to ``-infinity`` in row-value comparisons).
- ``created_at_ms`` is the Unix timestamp in milliseconds.
- ``row_id`` is the row UUID as a string.

The helper is intentionally unsigned — a user can fabricate pagination
state for their own rows (low-risk: they can only skip / re-show their
own history). HMAC is deferred to a follow-up if a tampering surface
emerges.

Lives at the top of ``src/`` to avoid colliding with the ``utils``
library package that ``services/api/src`` already exposes via
``from utils.api.endpoint import ...``.
"""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime


class InvalidCursorError(ValueError):
    """Raised when a cursor cannot be decoded."""


_NULL_ARCHIVED_SENTINEL = "-"
_MAX_CURSOR_LEN = 256


def encode_cursor(
    archived_at_ms: int | None,
    created_at_ms: int,
    row_id: str,
) -> str:
    """Encode a multi-key cursor.

    :param archived_at_ms: milliseconds since epoch, or ``None`` for
        rows where ``archived_at`` is NULL.
    :param created_at_ms: milliseconds since epoch.
    :param row_id: UUID string of the row.
    """
    arch = _NULL_ARCHIVED_SENTINEL if archived_at_ms is None else str(int(archived_at_ms))
    raw = f"{arch}|{int(created_at_ms)}|{row_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[int | None, int, str]:
    """Decode an opaque cursor into (archived_at_ms | None, created_at_ms, row_id).

    :raises InvalidCursorError: on any malformed input.
    """
    if not cursor or not isinstance(cursor, str):
        raise InvalidCursorError("cursor must be a non-empty string")
    if len(cursor) > _MAX_CURSOR_LEN:
        raise InvalidCursorError("cursor exceeds maximum length")

    # urlsafe_b64decode requires padding; re-add any stripped ``=``.
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise InvalidCursorError(f"cursor is not valid base64url: {exc}") from exc

    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidCursorError(f"cursor payload is not utf-8: {exc}") from exc

    parts = decoded.split("|")
    if len(parts) != 3:
        raise InvalidCursorError(
            f"cursor must have 3 fields separated by '|', got {len(parts)}"
        )

    arch_raw, created_raw, row_id = parts
    archived_at_ms: int | None
    if arch_raw == _NULL_ARCHIVED_SENTINEL:
        archived_at_ms = None
    else:
        try:
            archived_at_ms = int(arch_raw)
        except ValueError as exc:
            raise InvalidCursorError(
                f"cursor archived_at_ms is not an integer: {arch_raw!r}"
            ) from exc

    try:
        created_at_ms = int(created_raw)
    except ValueError as exc:
        raise InvalidCursorError(
            f"cursor created_at_ms is not an integer: {created_raw!r}"
        ) from exc

    if not row_id:
        raise InvalidCursorError("cursor row_id is empty")

    return (archived_at_ms, created_at_ms, row_id)


def datetime_to_ms(dt: datetime | None) -> int | None:
    """Convert a timezone-aware datetime to integer milliseconds since epoch.

    Returns ``None`` for a ``None`` input so call sites can feed nullable
    columns straight through. Naive datetimes are treated as UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)
