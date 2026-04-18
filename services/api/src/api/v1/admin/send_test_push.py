"""Admin test-push endpoint.

Fires a `NotificationType.TEST` push to the caller's own devices (or an
explicit target) so an admin can verify the FCM → APNs round-trip
deterministically. Rate-limited to keep the audit log / FCM quota safe
from jittery retries, and always writes an `error_logs` row with
`service="audit"` for the admin action (a second `service="push_notifications"`
row is added by `PushNotificationService` on send failure).
"""

from __future__ import annotations

import logging
import time

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import APIException, Endpoint, failure, success
from utils.classes.error_code import ErrorCode
from utils.models.error_log import ErrorLog
from utils.models.user import User
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)

logger = logging.getLogger(__name__)

# In-memory sliding window. Per-epic: acceptable because the admin surface
# is tiny (single-digit admins) and the worst case of a multi-instance API
# split is "10 requests / instance / minute" — still bounded. Redis-backed
# if this ever grows.
_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW_S = 60
_rate_limit_events: dict[str, list[float]] = {}


def _check_rate_limit(admin_user_id: str) -> tuple[bool, int]:
    """Return (ok, retry_after_s). ok=False means over-limit."""
    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW_S
    times = _rate_limit_events.setdefault(admin_user_id, [])
    times[:] = [t for t in times if t > cutoff]
    if len(times) >= _RATE_LIMIT_MAX:
        retry_after = int(times[0] + _RATE_LIMIT_WINDOW_S - now) + 1
        return False, max(retry_after, 1)
    times.append(now)
    return True, 0


def _reset_rate_limit_for_test() -> None:
    """Test-only hook — drops all rate-limit state."""
    _rate_limit_events.clear()


class SendTestPush(Endpoint):
    """Send a diagnostic FCM push (admin-only)."""

    def execute(
        self,
        params: SendTestPush.Params,
        force: bool = True,
    ):
        admin: User = self.user

        # Rate-limit FIRST — over-limit calls don't consume quota and don't
        # write audit rows (rate-limit hits are not admin actions).
        allowed, retry_after = _check_rate_limit(str(admin.id))
        if not allowed:
            logger.info(
                "push_notifications: admin test-push rate-limited admin_user=%s retry_after_s=%d",
                admin.id, retry_after,
            )
            return failure(
                status=429,
                error_code=ErrorCode.RATE_LIMITED.value,
                error_message=(
                    f"Too many test pushes (max {_RATE_LIMIT_MAX}/minute). "
                    f"Retry in {retry_after}s."
                ),
                data={
                    "ok": False,
                    "error": "rate_limited",
                    "retry_after_s": retry_after,
                },
            )

        # Resolve target (defaults to admin themselves)
        target_user_id = params.target_user_id or str(admin.id)
        target_user = self.db.execute(
            select(User).where(User.id == target_user_id)
        ).scalar_one_or_none()
        if target_user is None:
            raise APIException(
                status_code=404,
                detail=f"Target user not found: {target_user_id}",
                code=ErrorCode.NOT_FOUND,
            )

        title = (params.title or "Palateful test push").strip() or "Palateful test push"
        body = (params.body or "If you see this, pushes work 🍽️").strip() or "If you see this, pushes work 🍽️"

        notification = PushNotification(
            title=title,
            body=body,
            notification_type=NotificationType.TEST,
            data={"source": "admin_test", "route": "/"},
        )

        push_service = get_push_service()
        result = push_service.send_to_user(
            target_user,
            notification,
            db_session=self.db,
            force=force,
        )

        message_id = result.get("message_id")
        success_count = result.get("success_count", 0)
        failure_count = result.get("failure_count", 0)
        log_only = bool(result.get("log_only", False))
        quiet_hours_active = bool(result.get("quiet_hours_active", False))
        suppressed_by_quiet_hours = bool(result.get("suppressed_by_quiet_hours", False))
        tokens_registered = len(target_user.push_tokens or [])

        if success_count > 0:
            outcome = "ok"
        elif log_only:
            outcome = "log_only"
        elif suppressed_by_quiet_hours:
            outcome = "suppressed_quiet_hours"
        elif tokens_registered == 0:
            outcome = "no_tokens"
        else:  # pragma: no cover — defensive fallback when none of the known outcome states match
            outcome = "err"

        # Row 1: admin-action audit. Always written (except on rate-limit —
        # handled above). Mirrors promote_admin.py's shape: service="audit",
        # durable message string.
        audit_message = (
            f"admin:test_push target={target_user_id} by admin_user={admin.id} "
            f"result={outcome} message_id={message_id or 'none'}"
        )
        audit_row = ErrorLog(
            error_type="AdminTestPushAudit",
            error_message=audit_message,
            service="audit",
            user_id=target_user.id,
        )
        self.db.add(audit_row)
        self.db.commit()

        # Row 2 (service="push_notifications", PushSendFailure) is written
        # by PushNotificationService when a real FCM send errors. We don't
        # write it from here — keeps concerns split.

        ok = success_count > 0 or log_only or suppressed_by_quiet_hours or tokens_registered == 0

        return success(
            data=SendTestPush.Response(
                ok=ok,
                message_id=message_id,
                target_user_id=str(target_user.id),
                log_only=log_only,
                quiet_hours_active=quiet_hours_active,
                suppressed_by_quiet_hours=suppressed_by_quiet_hours,
                success_count=success_count,
                failure_count=failure_count,
                tokens_registered=tokens_registered,
                outcome=outcome,
            )
        )

    class Params(BaseModel):
        """Request body — all fields optional."""

        title: str | None = None
        body: str | None = None
        target_user_id: str | None = None

    class Response(BaseModel):
        """Response body.

        `ok` is true when the push was sent (or log-only/suppressed/no-tokens
        — deterministic outcomes that don't indicate a system error). `outcome`
        is the granular label for the dashboard: ok, log_only,
        suppressed_quiet_hours, no_tokens, err.
        """

        ok: bool
        message_id: str | None = None
        target_user_id: str
        log_only: bool
        quiet_hours_active: bool
        suppressed_by_quiet_hours: bool
        success_count: int
        failure_count: int
        tokens_registered: int
        outcome: str
