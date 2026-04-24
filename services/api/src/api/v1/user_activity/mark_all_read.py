"""Mark all activities as read endpoint."""

from sqlalchemy import update as sa_update
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.user import User
from utils.models.user_activity import UserActivity


class MarkAllRead(AsyncEndpoint):
    """Mark all of the current user's activities as read."""

    async def execute(self):
        user: User = self.user

        await self.db.execute(
            sa_update(UserActivity)
            .where(
                UserActivity.user_id == user.id,
                UserActivity.read.is_(False),
                UserActivity.archived_at.is_(None),
            )
            .values(read=True)
        )
        # Must commit — flush alone is rolled back on session close.
        await self.db.commit()

        return success()
