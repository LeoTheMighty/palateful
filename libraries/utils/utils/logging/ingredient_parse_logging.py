"""Audit logging for the ingredient parse-pass (eri-2 / eri-3a).

The JSON-LD ingredient parse pass runs ~text-only ingredient strings
through gpt-4o-mini with a strict JSON-schema response format. We emit
three distinct `error_logs` audit types so triage can separate them:

* ``IngredientParseFailure`` — one batch raised (rate limit, timeout,
  schema violation, 5xx). Caller fell back to returning the text-only
  inputs for that batch; partial success across batches is fine.
* ``IngredientParsePathological`` — caller was asked to parse more
  than ``max_total`` strings at once. The overflow is returned as
  text-only and we log once per import so the edge case is visible.
* ``IngredientFieldCoverage`` — once-per-import field-presence
  snapshot that powers the "how structured were today's imports?"
  production chart. Written whether or not the parse pass fired.

Each helper uses its own short-lived ``Database()`` session so the
caller's transaction can roll back without losing the audit row, and
never raises — audit paths must not break the import write path.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

INGREDIENT_PARSE_FAILURE_ERROR_TYPE = "IngredientParseFailure"
INGREDIENT_PARSE_PATHOLOGICAL_ERROR_TYPE = "IngredientParsePathological"
INGREDIENT_FIELD_COVERAGE_ERROR_TYPE = "IngredientFieldCoverage"

# Cap the JSON metadata we write into stack_trace so a malformed caller
# can't blow up the audit table.
_MAX_METADATA_BYTES = 4_000
_MAX_MESSAGE_LEN = 4_000


def _write_audit(
    *,
    error_type: str,
    message: str,
    metadata: dict[str, Any],
    import_item_id: Any = None,
) -> None:
    """Write a single ``service="audit"`` row. Never raises."""
    metadata_json = json.dumps(metadata, default=str, sort_keys=True)
    if len(metadata_json) > _MAX_METADATA_BYTES:
        metadata_json = metadata_json[:_MAX_METADATA_BYTES]
    message = message[:_MAX_MESSAGE_LEN]

    try:
        from utils.models.error_log import ErrorLog
        from utils.services.database import Database

        database = Database()
        try:
            row = ErrorLog(
                error_type=error_type,
                error_message=message,
                stack_trace=metadata_json,
                service="audit",
                import_item_id=import_item_id,
            )
            database.create(row)
        finally:
            database.close()
    except Exception:
        logger.exception(
            "Failed to write %s audit row (metadata=%s)", error_type, metadata
        )


def log_ingredient_parse_failure(
    *,
    error_class: str,
    batch_size: int,
    url_sample: str | None = None,
    extra: dict[str, Any] | None = None,
    import_item_id: Any = None,
) -> None:
    """One batch of the parse pass failed; caller fell back to text-only.

    ``error_class`` is the short name of the exception class or failure
    mode (``"RateLimitError"``, ``"TimeoutError"``, ``"SchemaViolation"``,
    ``"EmptyResponse"``, ``"APIError"``, etc.). ``batch_size`` is the
    number of strings in the failed batch so we can see whether we're
    hitting the 25-cap boundary or smaller tail batches.
    """
    metadata: dict[str, Any] = {
        "error_class": error_class,
        "batch_size": batch_size,
    }
    if url_sample:
        metadata["url_sample"] = url_sample[:200]
    if extra:
        metadata.update(extra)

    _write_audit(
        error_type=INGREDIENT_PARSE_FAILURE_ERROR_TYPE,
        message=f"Ingredient parse pass failed: {error_class} (batch={batch_size})",
        metadata=metadata,
        import_item_id=import_item_id,
    )


def log_ingredient_parse_pathological(
    *,
    total: int,
    max_total: int,
    url_sample: str | None = None,
    import_item_id: Any = None,
) -> None:
    """Caller asked to parse more than ``max_total`` strings — overflow
    returned as text-only. Log once per import so the edge case is
    visible without polluting the failure-rate metric.
    """
    metadata: dict[str, Any] = {
        "total": total,
        "max_total": max_total,
        "overflow": total - max_total,
    }
    if url_sample:
        metadata["url_sample"] = url_sample[:200]

    _write_audit(
        error_type=INGREDIENT_PARSE_PATHOLOGICAL_ERROR_TYPE,
        message=(
            f"Ingredient parse pass skipped: {total} strings exceeds "
            f"max_total={max_total}"
        ),
        metadata=metadata,
        import_item_id=import_item_id,
    )


def log_ingredient_field_coverage(
    *,
    total: int,
    qty_present: int,
    unit_present: int,
    name_present: int,
    notes_present: int,
    source: str,
    url_host: str | None = None,
    import_item_id: Any = None,
) -> None:
    """Field-presence snapshot for one import. ``source`` is one of
    ``"json_ld"`` (no parse pass fired — all rows were structured from
    JSON-LD), ``"json_ld_parse_pass"`` (text-only subset went through
    ``parse_ingredient_strings``), or ``"ai_extractor"`` (non-JSON-LD
    path).
    """
    metadata: dict[str, Any] = {
        "total": total,
        "qty_present": qty_present,
        "unit_present": unit_present,
        "name_present": name_present,
        "notes_present": notes_present,
        "source": source,
    }
    if url_host:
        metadata["url_host"] = url_host[:200]

    _write_audit(
        error_type=INGREDIENT_FIELD_COVERAGE_ERROR_TYPE,
        message=(
            f"Ingredient coverage: total={total} "
            f"qty={qty_present} unit={unit_present} "
            f"name={name_present} notes={notes_present} "
            f"source={source}"
        ),
        metadata=metadata,
        import_item_id=import_item_id,
    )
