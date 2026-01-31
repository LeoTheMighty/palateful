"""Get friend profile endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.friendship import Friendship
from utils.models.user import User


class GetFriend(Endpoint):
    """Get a friend's profile."""

    def execute(self, friend_id: str):
        """Get friend profile and friendship info."""
        user: User = self.user

        # Find friendship with friend data
        friendship = self.db.execute(
            select(Friendship)
            .options(joinedload(Friendship.friend))
            .where(
                Friendship.user_id == user.id,
                Friendship.friend_id == friend_id,
            )
        ).scalar_one_or_none()

        if not friendship:
            raise APIException(
                status_code=404,
                detail="This user is not your friend",
                code=ErrorCode.NOT_FOUND,
            )

        friend = friendship.friend

        return success(
            data=GetFriend.Response(
                id=str(friend.id),
                username=friend.username,
                name=friend.name,
                picture=friend.picture,
                friends_since=friendship.created_at,
            )
        )

    class Response(BaseModel):
        """Response model."""

        id: str
        username: str | None
        name: str | None
        picture: str | None
        friends_since: datetime
