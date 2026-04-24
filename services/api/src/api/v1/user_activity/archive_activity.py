"""Archive a single user activity.

Hides the activity from the default feed by setting `archived_at = NOW()`.
Idempotent: calling it on an already-archived row is a 200 no-op that
returns the existing timestamp.
"""

from datetime import UTC, datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User
from utils.models.user_activity import UserActivity


class ArchiveActivity(AsyncEndpoint):
    """Archive a user_activity row."""

    async def execute(self, activity_id: str):
        user: User = self.user

        activity = await self.database.find_by(
            UserActivity,
            id=activity_id,
            user_id=user.id,
        )
        if not activity:
            raise APIException(
                status_code=404,
                detail="Activity not found",
                code=ErrorCode.NOT_FOUND,
            )

        if activity.archived_at is None:
            activity.archived_at = datetime.now(UTC)
            self.database.db.add(activity)
            await self.database.db.commit()

        return success(
            data=ArchiveActivity.Response(
                id=str(activity.id),
                archived_at=activity.archived_at.isoformat(),
            )
        )

    class Response(BaseModel):
        id: str
        archived_at: str
