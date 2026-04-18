"""Unarchive a single user activity.

Restores the activity to the default feed by clearing `archived_at`.
Idempotent: calling it on an already-active row is a 200 no-op.
"""

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User
from utils.models.user_activity import UserActivity


class UnarchiveActivity(Endpoint):
    """Unarchive a user_activity row."""

    def execute(self, activity_id: str):
        user: User = self.user

        activity = self.database.find_by(
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

        if activity.archived_at is not None:
            activity.archived_at = None
            self.database.db.add(activity)
            self.database.db.commit()

        return success(data=UnarchiveActivity.Response(id=str(activity.id)))

    class Response(BaseModel):
        id: str
