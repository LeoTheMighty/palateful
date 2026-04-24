"""Accept friend request endpoint."""

from api.v1.friends.notifications import notify_friend_request_accepted
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.friend_request import FriendRequest
from utils.models.friendship import Friendship
from utils.models.user import User
from utils.services.notifications_bridge import notify_via_threadpool


class AcceptFriendRequest(AsyncEndpoint):
    """Accept a friend request."""

    async def execute(self, request_id: str):
        """Accept a friend request and create friendship."""
        user: User = self.user

        result = await self.db.execute(
            select(FriendRequest)
            .options(joinedload(FriendRequest.from_user))
            .where(FriendRequest.id == request_id)
        )
        friend_request = result.scalar_one_or_none()

        if not friend_request:
            raise APIException(
                status_code=404,
                detail="Friend request not found",
                code=ErrorCode.NOT_FOUND,
            )

        if friend_request.to_user_id != user.id:
            raise APIException(
                status_code=403,
                detail="You can only accept friend requests sent to you",
                code=ErrorCode.FORBIDDEN,
            )

        if friend_request.status != "pending":
            raise APIException(
                status_code=400,
                detail=f"This friend request has already been {friend_request.status}",
                code=ErrorCode.CONFLICT,
            )

        friend_request.status = "accepted"

        friendship1 = Friendship(
            user_id=user.id,
            friend_id=friend_request.from_user_id,
        )
        friendship2 = Friendship(
            user_id=friend_request.from_user_id,
            friend_id=user.id,
        )
        self.db.add(friendship1)
        self.db.add(friendship2)

        await self.db.commit()

        from_user = friend_request.from_user

        await notify_via_threadpool(
            notify_friend_request_accepted,
            str(from_user.id),
            user,
        )

        return success(
            data=AcceptFriendRequest.Response(
                success=True,
                friend=AcceptFriendRequest.UserInfo(
                    id=str(from_user.id),
                    username=from_user.username,
                    name=from_user.name,
                    picture=from_user.picture,
                ),
            )
        )

    class UserInfo(BaseModel):
        """Basic user info."""

        id: str
        username: str | None
        name: str | None
        picture: str | None

    class Response(BaseModel):
        """Response model."""

        success: bool
        friend: "AcceptFriendRequest.UserInfo"
