"""POST /v1/admin/dev-requests — an admin files a request for a change.

Workstream admin-request-intake (plan 1e84ad), PRD FR-1 … FR-4.

This is the only HTTP route that writes a `dev_requests` row, and it can
write exactly one shape: `status = 'submitted'`, `source = 'admin'`,
`target = 'palateful'`, `submitter_id` = the calling admin. Every other
status is the operator's to set, through `bin/prod-script` (PRD FR-12), so
the body forbids unknown keys — a client cannot smuggle `status`,
`submitter_id` or a pipeline field in.

The server, not the client, normalizes the three text fields (FR-2) and
hashes the normalized values, so what Leo reads at adoption is byte for
byte what an agent later reads, and either can recompute the hash.

No push fan-out and no Celery task: Leo hears about a request through the
bridge, which polls.

Rate limit: 5 creates per admin per rolling hour (FR-4), the in-memory
sliding window of `create_user_feedback.py`. Per process, so N API tasks
allow N × 5 — still bounded, and every request is admin-only.

Logging carries the row's id8 and the caller's id, never the text: a
request's text leaves this server once, in the operator's `adopt` record.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator
from utils.api.endpoint import AsyncEndpoint, failure, success
from utils.classes.error_code import ErrorCode
from utils.models.dev_request import (
    BODY_MAX_LENGTH,
    DEV_REQUEST_TARGET,
    DONE_WHEN_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    DevRequest,
    content_sha256,
    id8,
    normalize_request_text,
)
from utils.models.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate limit — 5 creates per admin per rolling hour (PRD FR-4).
# ---------------------------------------------------------------------------

_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW_S = 3600  # 1 hour
_rate_limit_events: dict[str, list[float]] = {}


def _check_rate_limit(user_id: str) -> tuple[bool, int]:
    """Return (ok, retry_after_s). ok=False means over-limit, and the call
    is not counted."""
    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW_S
    times = _rate_limit_events.setdefault(user_id, [])
    times[:] = [t for t in times if t > cutoff]
    if len(times) >= _RATE_LIMIT_MAX:
        retry_after = int(times[0] + _RATE_LIMIT_WINDOW_S - now) + 1
        return False, max(retry_after, 1)
    times.append(now)
    return True, 0


def _reset_rate_limit_for_test() -> None:
    """Test-only hook — drops all rate-limit state."""
    _rate_limit_events.clear()


def _normalized(value: str, field: str, max_length: int) -> str:
    """FR-2 normalization, then the limits, both on the normalized value so
    they agree with the table's CHECKs."""
    value = normalize_request_text(value)
    if not value:
        raise ValueError(f"{field} is blank after normalization")
    if len(value) > max_length:
        raise ValueError(
            f"{field} is {len(value)} characters after normalization; "
            f"the limit is {max_length}"
        )
    return value


def _unencodable_field(params: CreateDevRequest.Params) -> str | None:
    """The first field with no UTF-8 form, if any.

    JSON can carry a lone surrogate (``"\\ud800"``). FR-2 keeps it — it is
    category Cs, not Cc/Cf — but such text can be neither hashed nor stored.
    Checked here rather than in a validator because FastAPI's 422 body
    echoes the rejected input, which cannot be encoded either, so a
    validator's 422 becomes a 500 on the way out.
    """
    for field in ("title", "body", "done_when"):
        value = getattr(params, field)
        try:
            if value is not None:
                value.encode("utf-8")
        except UnicodeEncodeError:
            return field
    return None


class CreateDevRequest(AsyncEndpoint):
    """Create one `submitted` request for the calling admin."""

    async def execute(self, params: CreateDevRequest.Params):
        user: User = self.user

        bad_field = _unencodable_field(params)
        if bad_field is not None:
            return failure(
                status=422,
                error_code=ErrorCode.INVALID_REQUEST.value,
                error_message=f"{bad_field} is not valid Unicode text",
                data={"error": "invalid_text", "field": bad_field},
            )

        # Rate-limit next: an over-limit call creates no row.
        allowed, retry_after = _check_rate_limit(str(user.id))
        if not allowed:
            logger.info(
                "dev_request: rate-limited user=%s retry_after_s=%d",
                user.id,
                retry_after,
            )
            return failure(
                status=429,
                error_code=ErrorCode.RATE_LIMITED.value,
                error_message=(
                    f"Too many requests filed (max {_RATE_LIMIT_MAX}/hour). "
                    f"Retry in {retry_after}s."
                ),
                data={"error": "rate_limited", "retry_after_s": retry_after},
            )

        request = DevRequest(
            submitter_id=user.id,
            source="admin",
            title=params.title,
            body=params.body,
            done_when=params.done_when,
            content_sha256=content_sha256(params.title, params.body, params.done_when),
            target=DEV_REQUEST_TARGET,
            priority=params.priority,
            status="submitted",
            pr_urls=[],
        )
        self.db.add(request)
        await self.db.commit()
        await self.db.refresh(request)

        logger.info("dev_request: created %s user=%s", id8(request.id), user.id)
        return success(
            data=CreateDevRequest.Response(
                id=str(request.id),
                id8=id8(request.id),
                status=request.status,
                content_sha256=request.content_sha256,
                created_at=request.created_at,
            ),
            status=201,
        )

    class Params(BaseModel):
        """Request body. Unknown keys → 422 (`extra="forbid"`): `status`,
        `submitter_id` and every pipeline field are the operator's."""

        model_config = ConfigDict(extra="forbid")

        title: str
        body: str
        done_when: str | None = None
        priority: Literal["low", "normal", "high"] | None = None

        @field_validator("title")
        @classmethod
        def _title(cls, v: str) -> str:
            return _normalized(v, "title", TITLE_MAX_LENGTH)

        @field_validator("body")
        @classmethod
        def _body(cls, v: str) -> str:
            return _normalized(v, "body", BODY_MAX_LENGTH)

        @field_validator("done_when")
        @classmethod
        def _done_when(cls, v: str | None) -> str | None:
            if v is None:
                return None
            return _normalized(v, "done_when", DONE_WHEN_MAX_LENGTH)

    class Response(BaseModel):
        """201 body (FR-3). `id8` is the short handle the panel shows and
        the operator's records carry."""

        id: str
        id8: str
        status: str
        content_sha256: str
        created_at: datetime
