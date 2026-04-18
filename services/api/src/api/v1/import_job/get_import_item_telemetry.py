"""Get import item telemetry endpoint (irrd-2).

Returns a compact per-item stage log for the Flutter caret expansion.
Reads from `error_logs` filtered by `import_item_id` + a canonical
`stage` tag (written through `log_stage_transition`), groups rows per
stage, and synthesizes raw-output previews from the item's own
`raw_data` (parser stage) and `parsed_recipe` (extract stage).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import and_, asc
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.constants import (
    STAGE_CREATED,
    STAGE_EXTRACTED,
    STAGE_MATCHED,
    STAGE_PARSED,
)
from utils.models.error_log import ErrorLog
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User

# Canonical stage order — the expansion renders in this order regardless
# of when rows arrived.
_STAGE_ORDER: tuple[str, ...] = (
    STAGE_PARSED,
    STAGE_EXTRACTED,
    STAGE_MATCHED,
    STAGE_CREATED,
)

# Terminal statuses — any of these closes out a stage. "started" alone
# is rendered as the "in progress" state (still pending a terminal row).
_TERMINAL_STATUSES = frozenset({"ok", "failed", "skipped"})

_PREVIEW_MAX_CHARS = 4096


def _extract_status(stack_trace: str | None) -> str | None:
    """Pull the `status` key out of the audit row's JSON-encoded metadata."""
    if not stack_trace:
        return None
    try:
        payload = json.loads(stack_trace)
    except (ValueError, TypeError):
        return None
    status = payload.get("status") if isinstance(payload, dict) else None
    return str(status) if isinstance(status, str) else None


def _truncate(text: str | None, cap: int = _PREVIEW_MAX_CHARS) -> tuple[str | None, bool]:
    """Return (truncated_text, was_truncated) for a preview payload."""
    if text is None:
        return None, False
    if len(text) <= cap:
        return text, False
    return text[:cap], True


def _preview_for_parsed_stage(item: ImportItem) -> str | None:
    """Photo imports stash OCR text under `raw_data["text"]`; other source
    types have no human-readable parser-stage output."""
    raw = (item.raw_data or {}).get("text")
    if not raw:
        return None
    # Accept either a plain string (photo imports) or a list of strings
    # (parser-batch multi-group case). Join across groups with a clear
    # separator so the reader can tell where one page ends and the next
    # begins.
    if isinstance(raw, list):
        return "\n---\n".join(str(chunk) for chunk in raw if chunk)
    return str(raw)


def _preview_for_extracted_stage(item: ImportItem) -> str | None:
    """Pretty-print the parsed_recipe JSON so the expansion has something
    readable to surface in the Raw-Text section."""
    if not item.parsed_recipe:
        return None
    try:
        return json.dumps(
            item.parsed_recipe, indent=2, default=str, sort_keys=True
        )
    except (TypeError, ValueError):
        return None


class _StageAccumulator:
    """Rolls up audit rows for a single stage into a telemetry entry."""

    def __init__(self) -> None:
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.terminal_status: str | None = None

    def ingest(self, status: str | None, created_at: datetime) -> None:
        if status == "started":
            # Earliest started wins — the stage might re-run on retry, but
            # the caret expansion shows the original entry time until we
            # persist per-attempt rollups (out of scope for irrd-2).
            if self.started_at is None or created_at < self.started_at:
                self.started_at = created_at
            return
        if status in _TERMINAL_STATUSES and (
            self.completed_at is None or created_at > self.completed_at
        ):
            self.completed_at = created_at
            self.terminal_status = status

    def duration_ms(self) -> int | None:
        if self.started_at is None or self.completed_at is None:
            return None
        delta = self.completed_at - self.started_at
        ms = int(delta.total_seconds() * 1000)
        return ms if ms >= 0 else None

    def output_status(self) -> str:
        # Terminal row wins; otherwise, "started-only" surfaces as
        # `pending` (the caret treats it as "in flight"). No-rows-at-all
        # also surfaces as `pending` (unreached stage).
        return self.terminal_status or "pending"


class StageEntry(BaseModel):
    stage: Literal["parsed", "extracted", "matched", "created"]
    status: Literal["pending", "ok", "failed", "skipped"]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    raw_output_preview: str | None = None
    truncated: bool = False


class GetImportItemTelemetry(Endpoint):
    """Return a per-stage log for one import item.

    Response shape: `{ "stages": [ {stage, status, started_at,
    completed_at, duration_ms, raw_output_preview, truncated}, ... ] }`.
    The array is always 4 entries long in canonical stage order.
    """

    def execute(self, item_id: str) -> dict:
        user: User = self.user

        item = self.database.find_by(ImportItem, id=item_id)
        if not item:
            raise APIException(
                status_code=404,
                detail=f"Import item with ID '{item_id}' not found",
                code=ErrorCode.IMPORT_ITEM_NOT_FOUND,
            )

        job = self.database.find_by(ImportJob, id=item.import_job_id)
        if not job:
            raise APIException(
                status_code=404,
                detail="Import job not found",
                code=ErrorCode.IMPORT_JOB_NOT_FOUND,
            )

        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=job.recipe_book_id,
        )
        if not membership and job.user_id != user.id:
            raise APIException(
                status_code=403,
                detail="You don't have access to this import item",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        # Partial index `ix_error_logs_import_item_created` serves this
        # query (WHERE import_item_id = ? AND stage IS NOT NULL, ordered
        # by created_at). Legacy rows without a stage tag are filtered by
        # the `stage IN (_STAGE_ORDER)` predicate.
        rows = (
            self.database.db.query(ErrorLog)
            .filter(
                and_(
                    ErrorLog.import_item_id == item.id,
                    ErrorLog.stage.in_(_STAGE_ORDER),
                )
            )
            .order_by(asc(ErrorLog.created_at))
            .all()
        )

        accumulators: dict[str, _StageAccumulator] = {
            stage: _StageAccumulator() for stage in _STAGE_ORDER
        }
        for row in rows:
            stage = row.stage
            if stage not in accumulators:
                continue
            status = _extract_status(row.stack_trace)
            accumulators[stage].ingest(status, row.created_at)

        parsed_preview, parsed_trunc = _truncate(_preview_for_parsed_stage(item))
        extracted_preview, extracted_trunc = _truncate(
            _preview_for_extracted_stage(item)
        )

        # The `parsed` stage's preview always surfaces the item's own
        # raw_data, regardless of whether an audit row arrived. Same for
        # `extracted` and parsed_recipe. `matched` / `created` have no
        # human-readable output in irrd-2.
        preview_map: dict[str, tuple[str | None, bool]] = {
            STAGE_PARSED: (parsed_preview, parsed_trunc),
            STAGE_EXTRACTED: (extracted_preview, extracted_trunc),
            STAGE_MATCHED: (None, False),
            STAGE_CREATED: (None, False),
        }

        stages: list[StageEntry] = []
        for stage in _STAGE_ORDER:
            acc = accumulators[stage]
            preview_text, truncated = preview_map[stage]
            stages.append(
                StageEntry(
                    stage=stage,  # type: ignore[arg-type]
                    status=acc.output_status(),  # type: ignore[arg-type]
                    started_at=acc.started_at,
                    completed_at=acc.completed_at,
                    duration_ms=acc.duration_ms(),
                    raw_output_preview=preview_text,
                    truncated=truncated,
                )
            )

        return success(
            data=GetImportItemTelemetry.Response(
                item_id=str(item.id),
                stages=stages,
            )
        )

    class Response(BaseModel):
        item_id: str
        stages: list[StageEntry]
