"""Send friend request endpoint."""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.friend_request import FriendRequest
from utils.models.friendship import Friendship
from utils.models.user import User
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)

# Rate limit: max friend requests per day
MAX_REQUESTS_PER_DAY = 20


class SendFriendRequest(Endpoint):
    """Send a friend request to another user."""

    def execute(self, params: "SendFriendRequest.Params"):
        """Send a friend request."""
        user: User = self.user

        # Find target user by username or user_id
        if params.username:
            username = params.username.lower().strip()
            if username.startswith("@"):
                username = username[1:]

            target_user = self.db.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()

            if not target_user:
                raise APIException(
                    status_code=404,
                    detail=f"User @{username} not found",
                    code=ErrorCode.NOT_FOUND,
                )
        elif params.user_id:
            target_user = self.db.execute(
                select(User).where(User.id == params.user_id)
            ).scalar_one_or_none()

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

        # Can't send request to yourself
        if target_user.id == user.id:
            raise APIException(
                status_code=400,
                detail="You cannot send a friend request to yourself",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # Check if already friends
        existing_friendship = self.db.execute(
            select(Friendship).where(
                Friendship.user_id == user.id,
                Friendship.friend_id == target_user.id,
            )
        ).scalar_one_or_none()

        if existing_friendship:
            raise APIException(
                status_code=400,
                detail="You are already friends with this user",
                code=ErrorCode.CONFLICT,
            )

        # Check for existing request (either direction)
        existing_request = self.db.execute(
            select(FriendRequest).where(
                FriendRequest.status == "pending",
                or_(
                    # Request from current user to target
                    (FriendRequest.from_user_id == user.id)
                    & (FriendRequest.to_user_id == target_user.id),
                    # Request from target to current user
                    (FriendRequest.from_user_id == target_user.id)
                    & (FriendRequest.to_user_id == user.id),
                ),
            )
        ).scalar_one_or_none()

        if existing_request:
            if existing_request.from_user_id == user.id:
                raise APIException(
                    status_code=400,
                    detail="You already have a pending friend request to this user",
                    code=ErrorCode.CONFLICT,
                )
            else:
                # They already sent us a request - suggest accepting instead
                raise APIException(
                    status_code=400,
                    detail="This user already sent you a friend request. Accept it instead!",
                    code=ErrorCode.CONFLICT,
                )

        # Check rate limit
        day_ago = datetime.now(UTC) - timedelta(days=1)
        requests_today = self.db.execute(
            select(func.count(FriendRequest.id)).where(
                FriendRequest.from_user_id == user.id,
                FriendRequest.created_at >= day_ago,
            )
        ).scalar()

        if requests_today >= MAX_REQUESTS_PER_DAY:
            raise APIException(
                status_code=429,
                detail=f"You can only send {MAX_REQUESTS_PER_DAY} friend requests per day",
                code=ErrorCode.RATE_LIMITED,
            )

        # Create friend request
        friend_request = FriendRequest(
            from_user_id=user.id,
            to_user_id=target_user.id,
            message=params.message,
            status="pending",
        )
        self.db.add(friend_request)
        self.db.commit()
        self.db.refresh(friend_request)

        # Send push notification
        display_name = f"@{user.username}" if user.username else user.name or "Someone"
        push_service = get_push_service()
        push_service.send_to_user(
            target_user,
            PushNotification(
                title="Friend Request",
                body=f"{display_name} wants to be friends",
                notification_type=NotificationType.FRIEND_REQUEST,
                data={
                    "friend_request_id": str(friend_request.id),
                    "from_user_id": str(user.id),
                },
            ),
            db_session=self.db,
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
