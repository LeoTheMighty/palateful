"""Send friend request endpoint."""

from datetime import UTC, datetime, timedelta

from api.v1.friends.notifications import notify_friend_request_sent
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.friend_request import FriendRequest
from utils.models.friendship import Friendship
from utils.models.user import User
from utils.services.notifications_bridge import notify_via_threadpool

# Rate limit: max friend requests per day
MAX_REQUESTS_PER_DAY = 20


class SendFriendRequest(AsyncEndpoint):
    """Send a friend request to another user."""

    async def execute(self, params: "SendFriendRequest.Params"):
        """Send a friend request."""
        user: User = self.user

        if params.username:
            username = params.username.lower().strip()
            if username.startswith("@"):
                username = username[1:]

            target_result = await self.db.execute(
                select(User).where(User.username == username)
            )
            target_user = target_result.scalar_one_or_none()

            if not target_user:
                raise APIException(
                    status_code=404,
                    detail=f"User @{username} not found",
                    code=ErrorCode.NOT_FOUND,
                )
        elif params.user_id:
            target_result = await self.db.execute(
                select(User).where(User.id == params.user_id)
            )
            target_user = target_result.scalar_one_or_none()

            if not target_user:
                raise APIException(
                    status_code=404,
                    detail="User not found",
                    code=ErrorCode.NOT_FOUND,
                )
        else:
            raise APIException(
                status_code=400,
                detail="Either username or user_id is required",
                code=ErrorCode.VALIDATION_ERROR,
            )

        if target_user.id == user.id:
            raise APIException(
                status_code=400,
                detail="You cannot send a friend request to yourself",
                code=ErrorCode.VALIDATION_ERROR,
            )

        existing_friendship_result = await self.db.execute(
            select(Friendship).where(
                Friendship.user_id == user.id,
                Friendship.friend_id == target_user.id,
            )
        )
        existing_friendship = existing_friendship_result.scalar_one_or_none()

        if existing_friendship:
            raise APIException(
                status_code=400,
                detail="You are already friends with this user",
                code=ErrorCode.CONFLICT,
            )

        existing_request_result = await self.db.execute(
            select(FriendRequest).where(
                FriendRequest.status == "pending",
                or_(
                    (FriendRequest.from_user_id == user.id)
                    & (FriendRequest.to_user_id == target_user.id),
                    (FriendRequest.from_user_id == target_user.id)
                    & (FriendRequest.to_user_id == user.id),
                ),
            )
        )
        existing_request = existing_request_result.scalar_one_or_none()

        if existing_request:
            if existing_request.from_user_id == user.id:
                raise APIException(
                    status_code=400,
                    detail="You already have a pending friend request to this user",
                    code=ErrorCode.CONFLICT,
                )
            else:
                raise APIException(
                    status_code=400,
                    detail="This user already sent you a friend request. Accept it instead!",
                    code=ErrorCode.CONFLICT,
                )

        day_ago = datetime.now(UTC) - timedelta(days=1)
        rate_result = await self.db.execute(
            select(func.count(FriendRequest.id)).where(
                FriendRequest.from_user_id == user.id,
                FriendRequest.created_at >= day_ago,
            )
        )
        requests_today = rate_result.scalar()

        if requests_today >= MAX_REQUESTS_PER_DAY:
            raise APIException(
                status_code=429,
                detail=f"You can only send {MAX_REQUESTS_PER_DAY} friend requests per day",
                code=ErrorCode.RATE_LIMITED,
            )

        friend_request = FriendRequest(
            from_user_id=user.id,
            to_user_id=target_user.id,
            message=params.message,
            status="pending",
        )
        self.db.add(friend_request)
        await self.db.commit()
        await self.db.refresh(friend_request)

        await notify_via_threadpool(
            notify_friend_request_sent,
            str(target_user.id),
            str(friend_request.id),
            user,
        )

        return success(
            data=SendFriendRequest.Response(
                success=True,
                friend_request_id=str(friend_request.id),
                to_user=SendFriendRequest.UserInfo(
                    id=str(target_user.id),
                    username=target_user.username,
                    name=target_user.name,
                    picture=target_user.picture,
                ),
            )
        )

    class Params(BaseModel):
        """Request parameters."""

        username: str | None = None
        user_id: str | None = None
        message: str | None = None

    class UserInfo(BaseModel):
        """Basic user info."""

        id: str
        username: str | None
        name: str | None
        picture: str | None

    class Response(BaseModel):
        """Response model."""

        success: bool
        friend_request_id: str
        to_user: "SendFriendRequest.UserInfo"
