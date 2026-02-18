"""Claim invitations endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from utils.api.endpoint import Endpoint, success
from utils.models.invitation import Invitation
from utils.models.user import User


class ClaimInvitations(Endpoint):
    """Claim pending email invitations after signup.

    Matches current user's email against invitations where to_user_id is NULL.
    Sets to_user_id but does NOT auto-accept.
    """

    def execute(self):
        user: User = self.user

        if not user.email:
            return success(data=[])

        # Find pending invitations sent to this email with no user assigned
        invitations = self.db.execute(
            select(Invitation).where(
                func.lower(Invitation.to_email) == user.email.lower(),
                Invitation.to_user_id.is_(None),
                Invitation.status == "pending",
                Invitation.archived_at.is_(None),
            )
        ).scalars().all()

        claimed = []
        for inv in invitations:
            inv.to_user_id = user.id
            claimed.append(
                ClaimInvitations.ClaimedItem(
                    id=str(inv.id),
                    resource_type=inv.resource_type,
                    resource_id=str(inv.resource_id),
                    role_offered=inv.role_offered,
                    created_at=inv.created_at,
                )
            )

        if claimed:
            self.db.commit()

        return success(data=claimed)

    class ClaimedItem(BaseModel):
        id: str
        resource_type: str
        resource_id: str
        role_offered: str
        created_at: datetime
