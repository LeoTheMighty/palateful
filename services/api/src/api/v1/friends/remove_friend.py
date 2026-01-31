"""Remove friend endpoint."""

from pydantic import BaseModel
from sqlalchemy import or_, select
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.friendship import Friendship
from utils.models.user import User


class RemoveFriend(Endpoint):
    """Remove a friend."""

    def execute(self, friend_id: str):
        """Remove a friend (deletes bidirectional friendship)."""
        user: User = self.user

        # Find both friendship records
        friendships = self.db.execute(
            select(Friendship).where(
                or_(
                    (Friendship.user_id == user.id)
                    & (Friendship.friend_id == friend_id),
                    (Friendship.user_id == friend_id)
                    & (Friendship.friend_id == user.id),
                )
            )
        ).scalars().all()

        if not friendships:
            raise APIException(
                status_code=404,
                detail="Friendship not found",
                code=ErrorCode.NOT_FOUND,
            )

        # Delete both records
        for friendship in friendships:
            self.db.delete(friendship)

        self.db.commit()

        return success(
            data=RemoveFriend.Response(
                success=True,
                message="Friend removed",
            )
        )

    class Response(BaseModel):
        """Response model."""

        success: bool
        message: str
