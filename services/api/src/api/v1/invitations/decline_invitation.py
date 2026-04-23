"""Decline invitation endpoint."""

from datetime import UTC, datetime

from sqlalchemy import select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.invitation import Invitation
from utils.models.user import User


class DeclineInvitation(AsyncEndpoint):
    """Decline a received invitation."""

    async def execute(self, invitation_id: str):
        user: User = self.user

        result = await self.db.execute(
            select(Invitation).where(Invitation.id == invitation_id)
        )
        invitation = result.scalar_one_or_none()

        if not invitation:
            raise APIException(
                status_code=404,
                detail="Invitation not found",
                code=ErrorCode.INVITATION_NOT_FOUND,
            )

        if invitation.to_user_id != user.id:
            raise APIException(
                status_code=403,
                detail="You can only decline invitations sent to you",
                code=ErrorCode.INVITATION_ACCESS_DENIED,
            )

        if invitation.status != "pending":
            raise APIException(
                status_code=400,
                detail=f"This invitation has already been {invitation.status}",
                code=ErrorCode.INVITATION_NOT_PENDING,
            )

        invitation.status = "declined"
        invitation.responded_at = datetime.now(UTC)
        await self.db.commit()

        return success()
