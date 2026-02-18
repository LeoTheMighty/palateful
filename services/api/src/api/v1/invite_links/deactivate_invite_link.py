"""Deactivate invite link endpoint."""

from sqlalchemy import select
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.invite_link import InviteLink
from utils.models.user import User


class DeactivateInviteLink(Endpoint):
    """Deactivate an invite link."""

    def execute(self, invite_link_id: str):
        user: User = self.user

        invite_link = self.db.execute(
            select(InviteLink).where(
                InviteLink.id == invite_link_id,
                InviteLink.archived_at.is_(None),
            )
        ).scalar_one_or_none()

        if not invite_link:
            raise APIException(
                status_code=404,
                detail="Invite link not found",
                code=ErrorCode.INVITE_LINK_NOT_FOUND,
            )

        if invite_link.created_by_id != user.id:
            raise APIException(
                status_code=403,
                detail="You can only deactivate links you created",
                code=ErrorCode.INVITE_LINK_ACCESS_DENIED,
            )

        invite_link.is_active = False
        self.db.commit()

        return success()
