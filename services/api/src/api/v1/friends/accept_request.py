"""Accept friend request endpoint."""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload
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


class AcceptFriendRequest(Endpoint):
    """Accept a friend request."""

    def execute(self, request_id: str):
        """Accept a friend request and create friendship."""
        user: User = self.user

        # Find the friend request
        friend_request = self.db.execute(
            select(FriendRequest)
            .options(joinedload(FriendRequest.from_user))
            .where(FriendRequest.id == request_id)
        ).scalar_one_or_none()

        if not friend_request:
            raise APIException(
                status_code=404,
                detail="Friend request not found",
                code=ErrorCode.NOT_FOUND,
            )

        # Verify the request is to the current user
        if friend_request.to_user_id != user.id:
            raise APIException(
                status_code=403,
                detail="You can only accept friend requests sent to you",
                code=ErrorCode.FORBIDDEN,
            )

        # Check if request is still pending
        if friend_request.status != "pending":
            raise APIException(
                status_code=400,
                detail=f"This friend request has already been {friend_request.status}",
                code=ErrorCode.CONFLICT,
            )

        # Update request status
        friend_request.status = "accepted"

        # Create bidirectional friendships
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

        self.db.commit()

        # Send push notification to the requester
        from_user = friend_request.from_user
        display_name = f"@{user.username}" if user.username else user.name or "Someone"
        push_service = get_push_service()
        push_service.send_to_user(
            from_user,
            PushNotification(
                title="Friend Request Accepted",
                body=f"{display_name} accepted your friend request",
                notification_type=NotificationType.FRIEND_REQUEST_ACCEPTED,
                data={
                    "friend_id": str(user.id),
                },
            ),
            db_session=self.db,
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
