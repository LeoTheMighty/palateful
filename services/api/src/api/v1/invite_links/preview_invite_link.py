"""Preview invite link endpoint."""

from datetime import UTC, datetime

from api.v1.invitations.helpers import (
    check_existing_membership,
    get_resource_name,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.invite_link import InviteLink
from utils.models.user import User


class PreviewInviteLink(Endpoint):
    """Preview invite link metadata and state."""

    def execute(self, token: str):
        user: User = self.user

        invite_link = self.db.execute(
            select(InviteLink)
            .options(joinedload(InviteLink.created_by))
            .where(
                InviteLink.token == token,
                InviteLink.archived_at.is_(None),
            )
        ).scalar_one_or_none()

        if not invite_link:
            raise APIException(
                status_code=404,
                detail="Invite link not found",
                code=ErrorCode.INVITE_LINK_NOT_FOUND,
            )

        # Determine state
        now = datetime.now(UTC)
        if not invite_link.is_active:
            state = "inactive"
        elif invite_link.expires_at and invite_link.expires_at < now:
            state = "expired"
        elif invite_link.max_uses and invite_link.use_count >= invite_link.max_uses:
            state = "full"
        elif check_existing_membership(
            self.db, user.id, invite_link.resource_type, invite_link.resource_id
        ):
            state = "already_member"
        else:
            state = "active"

        resource_name = get_resource_name(
            self.db, invite_link.resource_type, invite_link.resource_id
        )
        created_by = invite_link.created_by

        return success(
            data=PreviewInviteLink.Response(
                token=invite_link.token,
                resource_type=invite_link.resource_type,
                resource_id=str(invite_link.resource_id),
                resource_name=resource_name,
                role_offered=invite_link.role_offered,
                state=state,
                created_by=PreviewInviteLink.UserInfo(
                    id=str(created_by.id),
                    username=created_by.username,
                    name=created_by.name,
                    picture=created_by.picture,
                ),
            )
        )

    class UserInfo(BaseModel):
        id: str
        username: str | None
        name: str | None
        picture: str | None

    class Response(BaseModel):
        token: str
        resource_type: str
        resource_id: str
        resource_name: str | None
        role_offered: str
        state: str
        created_by: "PreviewInviteLink.UserInfo"
