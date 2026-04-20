"""Audit logging for extractor-inferred field clamping / dropping.

efi-1 — every time the inference guardrails clamp a numeric value,
truncate a string, or drop an invalid vibe from an LLM-inferred field,
we emit an ``error_logs`` audit row so the correction-log dashboard can
see how often the model guessed something out-of-range.

``log_inferred_field_clamp`` is the **only** sanctioned way to write the
``InferredFieldClamped`` audit row. An AST-lint test
(``test_inference_log_enforcement.py``) fails CI if any other module
emits that ``error_type`` as a string literal.

Rules:
- Never raises. Audit must not break the extractor / task write path.
- Uses its own short-lived ``Database()`` so the caller's transaction
  can roll back without losing the audit row.
- Truncates the ``raw`` + ``clamped_or_dropped`` payloads defensively so
  a pathological LLM response can't blow up the audit table.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

INFERRED_FIELD_CLAMPED_ERROR_TYPE = "InferredFieldClamped"  # Single source of truth.

_MAX_VALUE_LEN = 500
_MAX_METADATA_BYTES = 4_000


def _stringify_and_truncate(value: Any) -> Any:
    """Defensive truncation for values that will land in the metadata JSON.

    Numeric / None values pass through unchanged. Strings and everything
    else are stringified and capped at ``_MAX_VALUE_LEN``.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value
    s = str(value)
    if len(s) > _MAX_VALUE_LEN:
        return s[:_MAX_VALUE_LEN]
    return s


def log_inferred_field_clamp(
    *,
    import_item_id: uuid.UUID | str | None,
    field: str,
    raw: Any,
    clamped_or_dropped: Any,
    reason: str,
) -> None:
    """Write one ``error_logs`` row for a guardrail clamp / drop event.

    Args:
        import_item_id: UUID of the ImportItem this clamp belongs to.
            ``None`` is allowed when the guardrails run pre-persistence
            (e.g. unit tests), in which case the row's
            ``import_item_id`` column stays null.
        field: The schema field name from ``INFERABLE_FIELDS`` whose
            value was clamped / truncated / dropped.
        raw: The original LLM-emitted value, before guardrails touched
            it.
        clamped_or_dropped: The post-guardrail value. For drops, this is
            ``None``. For clamps, this is the in-range value. For
            truncations, this is the truncated string.
        reason: Short token describing why the guardrail fired.
            Examples: ``"out_of_range"``, ``"too_long"``, ``"invalid_vibe"``.
    """
    field = (field or "").strip()
    reason = (reason or "").strip() or "unspecified"
    if not field:
        logger.warning(
            "Dropping inferred-field clamp log with empty field"
        )
        return

    item_uuid: uuid.UUID | None = None
    if import_item_id is not None:
        try:
            item_uuid = (
                import_item_id
                if isinstance(import_item_id, uuid.UUID)
                else uuid.UUID(str(import_item_id))
            )
        except (TypeError, ValueError):
            logger.warning(
                "Dropping inferred-field clamp log with non-uuid item id=%r",
                import_item_id,
            )
            return

    metadata: dict[str, Any] = {
        "field": field,
        "raw": _stringify_and_truncate(raw),
        "clamped_or_dropped": _stringify_and_truncate(clamped_or_dropped),
        "reason": reason,
    }
    metadata_json = json.dumps(metadata, default=str, sort_keys=True)
    if len(metadata_json) > _MAX_METADATA_BYTES:
        metadata_json = metadata_json[:_MAX_METADATA_BYTES]

    message = f"inferred_field:{field}:{reason}"

    try:
        # Local import to avoid a hard dependency from utils → SQLAlchemy
        # for callers that only want the constant.
        from utils.models.error_log import ErrorLog
        from utils.services.database import Database

        database = Database()
        try:
            row = ErrorLog(
                error_type=INFERRED_FIELD_CLAMPED_ERROR_TYPE,
                error_message=message[:4000],
                stack_trace=metadata_json,
                service="audit",
                import_item_id=item_uuid,
            )
            database.create(row)
        finally:
            database.close()
    except Exception:
        # Capture path must never fail the caller.
        logger.exception(
            "Failed to log InferredFieldClamped for item=%s field=%s reason=%s",
            item_uuid,
            field,
            reason,
        )
