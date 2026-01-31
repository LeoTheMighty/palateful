"""List friends endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from utils.api.endpoint import Endpoint, success
from utils.models.friendship import Friendship
from utils.models.user import User


class ListFriends(Endpoint):
    """List all friends for the current user."""

    def execute(self):
        """Get all friends."""
        user: User = self.user

        # Get all friendships with friend data
        friendships = (
            self.db.execute(
                select(Friendship)
                .options(joinedload(Friendship.friend))
                .where(Friendship.user_id == user.id)
                .order_by(Friendship.created_at.desc())
            )
            .scalars()
            .all()
        )

        # Build response
        friends = [
            ListFriends.FriendInfo(
                id=str(f.friend.id),
                username=f.friend.username,
                name=f.friend.name,
                picture=f.friend.picture,
                friends_since=f.created_at,
            )
            for f in friendships
        ]

        return success(
            data=ListFriends.Response(
                friends=friends,
                count=len(friends),
            )
        )

    class FriendInfo(BaseModel):
        """Friend info."""

        id: str
        username: str | None
        name: str | None
        picture: str | None
        friends_since: datetime

    class Response(BaseModel):
        """Response model."""

        friends: list["ListFriends.FriendInfo"]
        count: int
