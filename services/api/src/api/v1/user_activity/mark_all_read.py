"""Mark all activities as read endpoint."""

from utils.api.endpoint import Endpoint, success
from utils.models.user import User
from utils.models.user_activity import UserActivity


class MarkAllRead(Endpoint):
    """Mark all of the current user's activities as read."""

    def execute(self):
        user: User = self.user

        self.db.query(UserActivity).filter(
            UserActivity.user_id == user.id,
            UserActivity.read.is_(False),
            UserActivity.archived_at.is_(None),
        ).update({"read": True})
        # Must commit — flush alone is rolled back on session close.
        self.db.commit()

        return success()
