"""Mark single activity as read endpoint."""

from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User
from utils.models.user_activity import UserActivity


class MarkActivityRead(Endpoint):
    """Mark a single activity as read."""

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

        activity.read = True
        self.database.db.add(activity)
        self.database.db.flush()

        return success()
