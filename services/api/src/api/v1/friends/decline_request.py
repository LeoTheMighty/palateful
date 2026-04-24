"""Decline friend request endpoint."""

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.friend_request import FriendRequest
from utils.models.user import User


class DeclineFriendRequest(AsyncEndpoint):
    """Decline a friend request."""

    async def execute(self, request_id: str):
        """Decline a friend request."""
        user: User = self.user

        result = await self.db.execute(
            select(FriendRequest).where(FriendRequest.id == request_id)
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
                detail="You can only decline friend requests sent to you",
                code=ErrorCode.FORBIDDEN,
            )

        if friend_request.status != "pending":
            raise APIException(
                status_code=400,
                detail=f"This friend request has already been {friend_request.status}",
                code=ErrorCode.CONFLICT,
            )

        friend_request.status = "declined"
        await self.db.commit()

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
