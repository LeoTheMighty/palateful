"""Admin per-user push-health endpoint.

push-diag-3: one-click diagnostic for "I'm not getting pushes" reports.
Returns OS permission state, push-token count/prefixes, recent
`service="push_notifications"` error rows, and a Crashlytics link-out
filtered by the user's auth0 id. Read-only — writes a single
`service="audit"` row per call so the action is queryable. No new DB
tables; `last_successful_send_*` ships as `null` and is populated by a
future story if diagnosis actually needs it.
"""

from __future__ import annotations

import logging
import uuid

from pydantic import BaseModel
from sqlalchemy import and_, desc, func, select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.error_log import ErrorLog
from utils.models.user import User

logger = logging.getLogger(__name__)

_TOKEN_PREFIX_LEN = 8
_MESSAGE_TRUNCATE = 500
_DEFAULT_ERROR_LIMIT = 10
_MAX_ERROR_LIMIT = 50


def _token_prefix(token: str) -> str:
    if len(token) <= _TOKEN_PREFIX_LEN:
        return token
    return f"{token[:_TOKEN_PREFIX_LEN]}…"


def _build_crashlytics_url(auth0_id: str | None, fallback_user_id: str) -> str:
    """Crashlytics search URL filtered by the user's auth0 id.

    Crashlytics' user-search takes the value from `setUserIdentifier`
    (Flutter calls `ErrorReporter.setUserIdentifier(userId)` at login in
    `main.dart`). We pass the DB user_id (uuid) today, not the auth0_sub,
    so filter on that. If that changes, update both sides together.
    """
    identifier = auth0_id or fallback_user_id
    return (
        "https://console.firebase.google.com/project/palateful-prod/"
        f"crashlytics/app/ios:com.palateful.app/search?q={identifier}"
    )


class GetAdminPushHealth(AsyncEndpoint):
    """Per-user push health diagnostic (admin-only)."""

    async def execute(
        self,
        user_id_or_email: str,
        error_limit: int = _DEFAULT_ERROR_LIMIT,
    ):
        admin: User = self.user

        if error_limit < 1 or error_limit > _MAX_ERROR_LIMIT:
            raise APIException(
                status_code=400,
                detail=(
                    f"error_limit must be between 1 and {_MAX_ERROR_LIMIT}"
                ),
                code=ErrorCode.INVALID_REQUEST,
            )

        target = await _resolve_target(self.db, user_id_or_email)
        if target is None:
            raise APIException(
                status_code=404,
                detail=f"No user found for: {user_id_or_email}",
                code=ErrorCode.NOT_FOUND,
            )

        # Push tokens — JSONB list of raw FCM tokens on users.push_tokens.
        tokens = list(target.push_tokens or [])
        push_tokens_summary = [
            {"fcm_token_prefix": _token_prefix(t)} for t in tokens
        ]

        # Recent push-notifications error rows scoped to this user.
        error_rows = (await self.db.execute(
            select(ErrorLog)
            .where(
                and_(
                    ErrorLog.user_id == target.id,
                    ErrorLog.service == "push_notifications",
                )
            )
            .order_by(desc(ErrorLog.created_at))
            .limit(error_limit)
        )).scalars().all()

        recent_errors = [
            {
                "timestamp": (
                    row.created_at.isoformat() if row.created_at else None
                ),
                "error_type": row.error_type,
                "message": (
                    (row.error_message or "")[:_MESSAGE_TRUNCATE]
                    if row.error_message
                    else ""
                ),
                "request_id": row.request_id,
            }
            for row in error_rows
        ]

        crashlytics_url = _build_crashlytics_url(
            target.auth0_id, str(target.id)
        )

        # Audit row — single write per call, mirrors the promote_admin.py +
        # send_test_push shape.
        self.db.add(
            ErrorLog(
                error_type="AdminPushHealthCheck",
                error_message=(
                    f"admin:push_health_check target={target.id} "
                    f"by admin_user={admin.id}"
                ),
                service="audit",
                user_id=target.id,
            )
        )
        await self.db.commit()

        return success(
            data=GetAdminPushHealth.Response(
                user_id=str(target.id),
                email=target.email,
                notification_permission_status=target.notification_permission_status,
                push_tokens=push_tokens_summary,
                push_tokens_count=len(tokens),
                recent_errors=recent_errors,
                recent_errors_count=len(recent_errors),
                last_successful_send_at=None,
                last_successful_send_type=None,
                crashlytics_query_url=crashlytics_url,
            )
        )

    class Response(BaseModel):
        user_id: str
        email: str | None
        notification_permission_status: str | None
        push_tokens: list[dict]
        push_tokens_count: int
        recent_errors: list[dict]
        recent_errors_count: int
        last_successful_send_at: str | None
        last_successful_send_type: str | None
        crashlytics_query_url: str


async def _resolve_target(db, user_id_or_email: str) -> User | None:
    """Look up by UUID first, else by case-insensitive email match."""
    raw = user_id_or_email.strip()
    try:
        uid = uuid.UUID(raw)
        user = (await db.execute(
            select(User).where(User.id == uid)
        )).scalar_one_or_none()
        if user is not None:
            return user
    except (ValueError, TypeError):
        pass

    return (await db.execute(
        select(User).where(func.lower(User.email) == func.lower(raw))
    )).scalar_one_or_none()
