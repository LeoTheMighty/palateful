"""POST /v1/user/feedback — user-submitted feedback entry point.

Writes the feedback row, then enqueues a Celery fan-out task
(`notify_admins_new_feedback`) that sends a push + badge bump to every
active admin. Keeping the fan-out async means NFR53 (<500ms response
time) holds even with 5-10 admins on the FCM path.

Rate-limit: 10 submissions per user per rolling hour. In-memory sliding
window, mirroring the admin test-push rate-limit pattern in
`send_test_push.py`. Acceptable at friends-and-family scale; if the API
is ever split across multiple instances the worst case is N_instances
× 10/hour/user — still bounded, not abuse-vulnerable.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from utils.api.endpoint import AsyncEndpoint, failure, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User
from utils.models.user_feedback import (
    FEEDBACK_MAX_BODY_LENGTH,
    UserFeedback,
)
from utils.services.celery import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate limit — 10 submissions per user per rolling hour.
# In-memory sliding window, keyed by user_id. Matches the precedent set by
# admin `send_test_push.py`. Replace with Redis-backed if we ever scale out.
# ---------------------------------------------------------------------------

_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW_S = 3600  # 1 hour
_rate_limit_events: dict[str, list[float]] = {}


def _check_rate_limit(user_id: str) -> tuple[bool, int]:
    """Return (ok, retry_after_s). ok=False means over-limit."""
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


# ---------------------------------------------------------------------------
# Tight context envelope. Unknown keys → 422 at Pydantic validation time.
# ---------------------------------------------------------------------------


class FeedbackContext(BaseModel):
    """Strict context envelope sent by the Flutter client.

    Users submit knowing the admin sees this — keep the surface minimal.
    Any unknown key is rejected at validation time (model_config: extra=forbid)
    so we don't silently accept unexpected fingerprinting attempts.
    """

    model_config = ConfigDict(extra="forbid")

    app_version: str | None = Field(default=None, max_length=64)
    platform: Literal["ios", "android", "web"] | None = None
    route: str | None = Field(default=None, max_length=512)
    recipe_id: uuid.UUID | None = None


class CreateUserFeedback(AsyncEndpoint):
    """Create a new feedback entry for the current user."""

    async def execute(self, params: CreateUserFeedback.Params):
        user: User = self.user

        # Rate-limit FIRST — over-limit calls must not create rows or enqueue
        # fan-out tasks. Same ordering as admin test-push.
        allowed, retry_after = _check_rate_limit(str(user.id))
        if not allowed:
            logger.info(
                "user_feedback: rate-limited user=%s retry_after_s=%d",
                user.id, retry_after,
            )
            return failure(
                status=429,
                error_code=ErrorCode.RATE_LIMITED.value,
                error_message=(
                    f"Too many feedback submissions (max {_RATE_LIMIT_MAX}/hour). "
                    f"Retry in {retry_after}s."
                ),
                data={
                    "error": "rate_limited",
                    "retry_after_s": retry_after,
                },
            )

        context_dict: dict | None = None
        if params.context is not None:
            # mode='json' so UUID serialises to str in the JSONB payload
            context_dict = params.context.model_dump(mode="json", exclude_none=True)

        feedback = UserFeedback(
            user_id=user.id,
            body=params.body,
            category=params.category,
            context=context_dict,
            status="unread",
        )
        self.db.add(feedback)
        await self.db.commit()
        await self.db.refresh(feedback)

        # Fire-and-forget admin fan-out. The task itself is defined in story 2;
        # we dispatch by name so story 1 can land without the task implementation.
        try:
            celery_app.send_task(
                "notify_admins_new_feedback",
                args=[str(feedback.id)],
            )
        except Exception as e:  # noqa: BLE001 — never break the user response
            logger.error(
                "user_feedback: failed to enqueue admin fan-out feedback_id=%s err=%s: %s",
                feedback.id, type(e).__name__, e,
            )

        return success(
            data=CreateUserFeedback.Response(
                id=str(feedback.id),
                status=feedback.status,
            ),
            status=201,
        )

    class Params(BaseModel):
        """Request body for POST /v1/user/feedback.

        `body`: 1..4000 chars (matches DB CHECK constraint).
        `category`: optional, one of ('bug','idea','praise','other').
        `context`: optional strict envelope — unknown keys raise 422.
        """

        model_config = ConfigDict(extra="forbid")

        body: str = Field(min_length=1, max_length=FEEDBACK_MAX_BODY_LENGTH)
        category: Literal["bug", "idea", "praise", "other"] | None = None
        context: FeedbackContext | None = None

        @field_validator("body")
        @classmethod
        def _strip_body_reject_blank(cls, v: str) -> str:
            stripped = v.strip()
            if not stripped:
                raise ValueError("body cannot be blank")
            return stripped

    class Response(BaseModel):
        """Response body — just the ID and status so the client can
        optimistically render a 'sent' state without another fetch."""

        id: str
        status: str
