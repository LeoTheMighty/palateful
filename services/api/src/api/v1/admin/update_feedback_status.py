"""PUT /v1/admin/feedback/{feedback_id}/status — transition feedback status.

Allowed transitions: any → any (unread ↔ read ↔ archived). Archive is only
terminal by UX convention, not enforcement. Writes an audit row to
error_logs on every transition; no-op transitions (same → same) still
write the row so the admin's action shows up in history.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.error_log import ErrorLog
from utils.models.user import User
from utils.models.user_feedback import UserFeedback


class UpdateFeedbackStatus(AsyncEndpoint):
    """Flip the status of a single feedback row."""

    async def execute(
        self,
        feedback_id: str,
        params: UpdateFeedbackStatus.Params,
    ):
        admin: User = self.user

        feedback = (await self.db.execute(
            select(UserFeedback).where(UserFeedback.id == feedback_id)
        )).scalar_one_or_none()

        if feedback is None:
            raise APIException(
                status_code=404,
                detail=f"Feedback not found: {feedback_id}",
                code=ErrorCode.NOT_FOUND,
            )

        old_status = feedback.status
        new_status = params.status

        feedback.status = new_status
        # Touch updated_at explicitly so the DB onupdate hook fires even
        # for SQLAlchemy backends that skip it on no-op writes.
        feedback.updated_at = datetime.utcnow()

        audit = ErrorLog(
            error_type="FeedbackStatusChange",
            error_message=(
                f"feedback={feedback.id} from={old_status} to={new_status} "
                f"by_admin={admin.id}"
            ),
            service="audit",
            user_id=feedback.user_id,
        )
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(feedback)

        return success(
            data=UpdateFeedbackStatus.Response(
                id=str(feedback.id),
                status=feedback.status,
                updated_at=(
                    feedback.updated_at.isoformat()
                    if feedback.updated_at
                    else None
                ),
            )
        )

    class Params(BaseModel):
        status: Literal["unread", "read", "archived"]

    class Response(BaseModel):
        id: str
        status: str
        updated_at: str | None = None
