"""Cancel friend request endpoint."""

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.friend_request import FriendRequest
from utils.models.user import User


class CancelFriendRequest(Endpoint):
    """Cancel a sent friend request."""

    def execute(self, request_id: str):
        """Cancel a friend request that the current user sent."""
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

        # Verify the request is from the current user
        if friend_request.from_user_id != user.id:
            raise APIException(
                status_code=403,
                detail="You can only cancel friend requests that you sent",
                code=ErrorCode.FORBIDDEN,
            )

        # Check if request is still pending
        if friend_request.status != "pending":
            raise APIException(
                status_code=400,
                detail=f"This friend request has already been {friend_request.status}",
                code=ErrorCode.CONFLICT,
            )

        # Delete the request
        self.db.delete(friend_request)
        self.db.commit()

        return success(
            data=CancelFriendRequest.Response(
                success=True,
                message="Friend request cancelled",
            )
        )

    class Response(BaseModel):
        """Response model."""

        success: bool
        message: str
