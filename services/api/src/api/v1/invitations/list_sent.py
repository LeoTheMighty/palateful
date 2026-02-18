"""List sent invitations endpoint."""

from datetime import datetime

from api.v1.invitations.helpers import get_resource_name
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from utils.api.endpoint import Endpoint, success
from utils.models.invitation import Invitation
from utils.models.user import User


class ListSentInvitations(Endpoint):
    """List invitations sent by the current user."""

    def execute(self):
        user: User = self.user

        invitations = self.db.execute(
            select(Invitation)
            .options(joinedload(Invitation.to_user))
            .where(
                Invitation.from_user_id == user.id,
                Invitation.archived_at.is_(None),
            )
            .order_by(Invitation.created_at.desc())
        ).scalars().unique().all()

        items = []
        for inv in invitations:
            resource_name = get_resource_name(
                self.db, inv.resource_type, inv.resource_id
            )
            to_user_info = None
            if inv.to_user:
                to_user_info = ListSentInvitations.UserInfo(
                    id=str(inv.to_user.id),
                    username=inv.to_user.username,
                    name=inv.to_user.name,
                    picture=inv.to_user.picture,
                )

            items.append(
                ListSentInvitations.InvitationItem(
                    id=str(inv.id),
                    resource_type=inv.resource_type,
                    resource_id=str(inv.resource_id),
                    resource_name=resource_name,
                    role_offered=inv.role_offered,
                    status=inv.status,
                    message=inv.message,
                    to_email=inv.to_email,
                    created_at=inv.created_at,
                    expires_at=inv.expires_at,
                    responded_at=inv.responded_at,
                    to_user=to_user_info,
                )
            )

        return success(data=items)

    class UserInfo(BaseModel):
        id: str
        username: str | None
        name: str | None
        picture: str | None

    class InvitationItem(BaseModel):
        id: str
        resource_type: str
        resource_id: str
        resource_name: str | None
        role_offered: str
        status: str
        message: str | None
        to_email: str | None
        created_at: datetime
        expires_at: datetime | None
        responded_at: datetime | None
        to_user: "ListSentInvitations.UserInfo | None"
