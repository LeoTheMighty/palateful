"""Cancel friend request endpoint."""

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.friend_request import FriendRequest
from utils.models.user import User


class CancelFriendRequest(AsyncEndpoint):
    """Cancel a sent friend request."""

    async def execute(self, request_id: str):
        """Cancel a friend request that the current user sent."""
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

        if friend_request.from_user_id != user.id:
            raise APIException(
                status_code=403,
                detail="You can only cancel friend requests that you sent",
                code=ErrorCode.FORBIDDEN,
            )

        if friend_request.status != "pending":
            raise APIException(
                status_code=400,
                detail=f"This friend request has already been {friend_request.status}",
                code=ErrorCode.CONFLICT,
            )

        await self.db.delete(friend_request)
        await self.db.commit()

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
