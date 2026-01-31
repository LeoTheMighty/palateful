"""Decline friend request endpoint."""

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.friend_request import FriendRequest
from utils.models.user import User


class DeclineFriendRequest(Endpoint):
    """Decline a friend request."""

    def execute(self, request_id: str):
        """Decline a friend request."""
        user: User = self.user

        # Find the friend request
        friend_request = self.db.execute(
            select(FriendRequest).where(FriendRequest.id == request_id)
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
                detail="You can only decline friend requests sent to you",
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
        friend_request.status = "declined"
        self.db.commit()

        return success(
            data=DeclineFriendRequest.Response(
                success=True,
                message="Friend request declined",
            )
        )

    class Response(BaseModel):
        """Response model."""

        success: bool
        message: str
