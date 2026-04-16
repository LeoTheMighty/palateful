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
        # flush() alone sends SQL but leaves an open transaction that
        # gets rolled back when the session closes at end-of-request.
        # commit() is required to actually persist the read state —
        # without it, GET /v1/activities always returns the same
        # unread items. Reported bug: Activity tab always shows unread.
        self.database.db.commit()

        return success()
