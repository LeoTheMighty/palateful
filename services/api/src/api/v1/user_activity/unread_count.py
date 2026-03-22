"""Unread activity count endpoint."""

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.user import User
from utils.models.user_activity import UserActivity


class UnreadCount(Endpoint):
    """Get unread activity count for badge display."""

    def execute(self):
        user: User = self.user

        count = (
            self.db.query(UserActivity)
            .filter(
                UserActivity.user_id == user.id,
                UserActivity.read.is_(False),
                UserActivity.archived_at.is_(None),
            )
            .count()
        )

        return success(data=UnreadCount.Response(count=count))

    class Response(BaseModel):
        count: int
