"""Audit logging for import-item stage transitions.

The Flutter caret expansion (irrd-4/-5) renders a 4-stage timeline per
import item, derived server-side by
`GetImportItemTelemetry`. That endpoint reads from `error_logs` filtered
by `import_item_id` + a canonical `stage` tag.

`log_stage_transition` is the **only** sanctioned way to write a
stage-transition audit row. An AST-lint test
(`test_stage_transition_enforcement.py`) fails CI if any other module
emits `"StageTransition"` as a literal.

Rules:
- Never raises. Audit must not break the import-task write path.
- Uses its own short-lived `Database()` so the caller's transaction can
  roll back (e.g. on an extractor failure) without losing the audit row
  that says "matched stage failed at <time>".
- Truncates `raw_output_preview` defensively at 4096 chars at the write
  side too, not just the read side. A misbehaving caller passing a 10MB
  blob can't blow up the audit table.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

STAGE_TRANSITION_ERROR_TYPE = "StageTransition"  # Single source of truth.

# Canonical stage tokens. Kept in-module rather than importing
# `utils.constants.STAGE_*` so the helper works even if the constants
# module gains a new stage the caller hasn't yet updated.
_ALLOWED_STAGES = frozenset({"parsed", "extracted", "matched", "created"})

# Canonical status vocabulary for the `status` arg. `started` marks
# entry to a stage; the terminal trio records exit. The telemetry
# endpoint maps "started with no terminal row yet" → output status
# `pending`.
_ALLOWED_STATUSES = frozenset({"started", "ok", "failed", "skipped"})

_MAX_PREVIEW_CHARS = 4096
_MAX_METADATA_BYTES = 8_000


def log_stage_transition(
    *,
    import_item_id: uuid.UUID | str,
    stage: str,
    status: str,
    error_message: str | None = None,
    raw_output_preview: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write one `error_logs` row for an import-stage transition.

    Args:
        import_item_id: UUID of the ImportItem this transition belongs
            to. Accepted as str or UUID.
        stage: One of "parsed", "extracted", "matched", "created".
        status: One of "started", "ok", "failed", "skipped".
        error_message: Short human-readable error. Persisted in the
            canonical `error_message` column. If not provided, a
            synthetic `"{stage}:{status}"` is written so the row is
            never null-message.
        raw_output_preview: Optional UTF-8 string capturing the raw
            parser/extractor output at this transition. Truncated to
            4096 chars defensively.
        metadata: Optional extra context dict merged into the
            JSON-encoded `stack_trace` column (where we stuff audit
            metadata — not a real stack trace for these rows).
    """
    # Defensive normalization. Silently coerce rather than raise, since
    # audit is best-effort and should never break the caller.
    stage = (stage or "").strip()
    status = (status or "").strip()

    if stage not in _ALLOWED_STAGES:
        logger.warning(
            "Dropping stage-transition log with unknown stage=%r", stage
        )
        return
    if status not in _ALLOWED_STATUSES:
        logger.warning(
            "Dropping stage-transition log with unknown status=%r", status
        )
        return

    try:
        item_uuid = (
            import_item_id
            if isinstance(import_item_id, uuid.UUID)
            else uuid.UUID(str(import_item_id))
        )
    except (TypeError, ValueError):
        logger.warning(
            "Dropping stage-transition log with non-uuid item id=%r",
            import_item_id,
        )
        return

    truncated_preview: str | None = None
    if raw_output_preview is not None:
        truncated_preview = str(raw_output_preview)[:_MAX_PREVIEW_CHARS]

    audit_metadata: dict[str, Any] = {"status": status}
    if truncated_preview is not None:
        audit_metadata["raw_output_preview"] = truncated_preview
        audit_metadata["preview_truncated"] = len(
            str(raw_output_preview)
        ) > _MAX_PREVIEW_CHARS
    if metadata:
        # Don't let the caller overwrite reserved keys.
        for k, v in metadata.items():
            if k in {"status", "raw_output_preview", "preview_truncated"}:
                continue
            audit_metadata[k] = v

    metadata_json = json.dumps(audit_metadata, default=str, sort_keys=True)
    if len(metadata_json) > _MAX_METADATA_BYTES:
        metadata_json = metadata_json[:_MAX_METADATA_BYTES]

    message = error_message or f"{stage}:{status}"

    try:
        # Local import to avoid a hard dependency from utils → SQLAlchemy
        # for callers that only want the constant.
        from utils.models.error_log import ErrorLog
        from utils.services.database import Database

        database = Database()
        try:
            row = ErrorLog(
                error_type=STAGE_TRANSITION_ERROR_TYPE,
                error_message=message[:4000],
                stack_trace=metadata_json,
                service="audit",
                import_item_id=item_uuid,
                stage=stage,
            )
            database.create(row)
        finally:
            database.close()
    except Exception:
        # Capture path must never fail the caller.
        logger.exception(
            "Failed to log stage transition for item=%s stage=%s status=%s",
            item_uuid,
            stage,
            status,
        )
