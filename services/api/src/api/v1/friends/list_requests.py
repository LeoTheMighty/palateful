"""List friend requests endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.friend_request import FriendRequest
from utils.models.user import User


class ListFriendRequests(AsyncEndpoint):
    """List all pending friend requests (sent and received)."""

    async def execute(self):
        """Get pending friend requests."""
        user: User = self.user

        received_result = await self.db.execute(
            select(FriendRequest)
            .options(joinedload(FriendRequest.from_user))
            .where(
                FriendRequest.to_user_id == user.id,
                FriendRequest.status == "pending",
            )
            .order_by(FriendRequest.created_at.desc())
        )
        received = list(received_result.scalars().all())

        sent_result = await self.db.execute(
            select(FriendRequest)
            .options(joinedload(FriendRequest.to_user))
            .where(
                FriendRequest.from_user_id == user.id,
                FriendRequest.status == "pending",
            )
            .order_by(FriendRequest.created_at.desc())
        )
        sent = list(sent_result.scalars().all())

        received_requests = [
            ListFriendRequests.FriendRequestInfo(
                id=str(r.id),
                from_user=ListFriendRequests.UserInfo(
                    id=str(r.from_user.id),
                    username=r.from_user.username,
                    name=r.from_user.name,
                    picture=r.from_user.picture,
                ),
                message=r.message,
                created_at=r.created_at,
            )
            for r in received
        ]

        sent_requests = [
            ListFriendRequests.SentRequestInfo(
                id=str(r.id),
                to_user=ListFriendRequests.UserInfo(
                    id=str(r.to_user.id),
                    username=r.to_user.username,
                    name=r.to_user.name,
                    picture=r.to_user.picture,
                ),
                message=r.message,
                created_at=r.created_at,
            )
            for r in sent
        ]

        return success(
            data=ListFriendRequests.Response(
                received=received_requests,
                sent=sent_requests,
                received_count=len(received_requests),
                sent_count=len(sent_requests),
            )
        )

    class UserInfo(BaseModel):
        """Basic user info."""

        id: str
        username: str | None
        name: str | None
        picture: str | None

    class FriendRequestInfo(BaseModel):
        """Received friend request info."""

        id: str
        from_user: "ListFriendRequests.UserInfo"
        message: str | None
        created_at: datetime

    class SentRequestInfo(BaseModel):
        """Sent friend request info."""

        id: str
        to_user: "ListFriendRequests.UserInfo"
        message: str | None
        created_at: datetime

    class Response(BaseModel):
        """Response model."""

        received: list["ListFriendRequests.FriendRequestInfo"]
        sent: list["ListFriendRequests.SentRequestInfo"]
        received_count: int
        sent_count: int
