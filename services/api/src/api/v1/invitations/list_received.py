"""List received invitations endpoint."""

from datetime import UTC, datetime

from api.v1.invitations.helpers import get_resource_name
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.invitation import Invitation
from utils.models.user import User


class ListReceivedInvitations(AsyncEndpoint):
    """List pending invitations received by the current user."""

    async def execute(self):
        user: User = self.user
        now = datetime.now(UTC)

        result = await self.db.execute(
            select(Invitation)
            .options(joinedload(Invitation.from_user))
            .where(
                Invitation.to_user_id == user.id,
                Invitation.status == "pending",
                Invitation.archived_at.is_(None),
            )
            .order_by(Invitation.created_at.desc())
        )
        invitations = result.scalars().unique().all()

        items = []
        for inv in invitations:
            # Skip expired
            if inv.expires_at and inv.expires_at < now:
                continue

            resource_name = await get_resource_name(
                self.db, inv.resource_type, inv.resource_id
            )
            from_user = inv.from_user
            items.append(
                ListReceivedInvitations.InvitationItem(
                    id=str(inv.id),
                    resource_type=inv.resource_type,
                    resource_id=str(inv.resource_id),
                    resource_name=resource_name,
                    role_offered=inv.role_offered,
                    message=inv.message,
                    created_at=inv.created_at,
                    expires_at=inv.expires_at,
                    from_user=ListReceivedInvitations.UserInfo(
                        id=str(from_user.id),
                        username=from_user.username,
                        name=from_user.name,
                        picture=from_user.picture,
                    ),
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
        message: str | None
        created_at: datetime
        expires_at: datetime | None
        from_user: "ListReceivedInvitations.UserInfo"
