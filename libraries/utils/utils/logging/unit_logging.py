"""Audit logging for unit-normalization misses.

The `unit_aliases` table is a curated, growing resource. Whenever
`normalize_unit_display` sees a freeform string that isn't already
canonical and isn't in the alias map, we want to know — both so we can
add the alias to the seed migration in a future story, and so we can
spot extractor regressions.

`log_unit_alias_miss` is the **only** sanctioned way to write the
`UnitAliasMiss` audit row. An AST-lint test
(`test_unit_alias_miss_enforcement.py`) fails CI if any other module
emits an `error_logs` row with that `error_type`.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

UNIT_ALIAS_MISS_ERROR_TYPE = "UnitAliasMiss"  # Single source of truth.

# Keep payloads bounded. Aliases are short by design (≤80 chars in the
# DB) but a misbehaving caller could pass a 1MB blob. Truncate
# defensively so a bug here can't blow up the audit table.
_MAX_RAW_LEN = 200
_MAX_METADATA_BYTES = 2_000


def log_unit_alias_miss(raw: str, context: dict[str, Any] | None = None) -> None:
    """Write one `error_logs` row for an unrecognized unit string.

    Uses its own short-lived `Database()` so the caller's transaction
    can roll back without losing the audit row. Never raises — this is
    audit-only and must not break the write path.
    """
    truncated_raw = (raw or "")[:_MAX_RAW_LEN]
    metadata: dict[str, Any] = {"raw": truncated_raw}
    if context:
        metadata.update(context)

    metadata_json = json.dumps(metadata, default=str, sort_keys=True)
    if len(metadata_json) > _MAX_METADATA_BYTES:
        metadata_json = metadata_json[:_MAX_METADATA_BYTES]

    try:
        # Local import to avoid a hard dependency from utils → SQLAlchemy
        # for callers that only want the constant.
        from utils.models.error_log import ErrorLog
        from utils.services.database import Database

        database = Database()
        try:
            row = ErrorLog(
                error_type=UNIT_ALIAS_MISS_ERROR_TYPE,
                error_message=f"Unrecognized unit token: {truncated_raw!r}",
                stack_trace=metadata_json,
                service="audit",
            )
            database.create(row)
        finally:
            database.close()
    except Exception:
        # Capture path must never fail the caller.
        logger.exception(
            "Failed to log UnitAliasMiss for raw=%r", truncated_raw
        )
