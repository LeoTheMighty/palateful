"""Create invite link endpoint."""

import secrets
from datetime import UTC, datetime, timedelta

from api.v1.invitations.helpers import (
    check_resource_permission,
    validate_resource_and_role,
)
from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.invite_link import InviteLink
from utils.models.user import User


class CreateInviteLink(Endpoint):
    """Create a shareable invite link for a resource."""

    def execute(self, params: "CreateInviteLink.Params"):
        user: User = self.user

        validate_resource_and_role(params.resource_type, params.role_offered)
        check_resource_permission(
            self.db, user.id, params.resource_type, params.resource_id
        )

        token = secrets.token_urlsafe(15)[:20]

        expires_at = None
        if params.expires_in_days:
            expires_at = datetime.now(UTC) + timedelta(days=params.expires_in_days)

        invite_link = InviteLink(
            token=token,
            created_by_id=user.id,
            resource_type=params.resource_type,
            resource_id=params.resource_id,
            role_offered=params.role_offered,
            max_uses=params.max_uses,
            expires_at=expires_at,
        )
        self.db.add(invite_link)
        self.db.commit()
        self.db.refresh(invite_link)

        return success(
            data=CreateInviteLink.Response(
                id=str(invite_link.id),
                token=invite_link.token,
                resource_type=invite_link.resource_type,
                resource_id=str(invite_link.resource_id),
                role_offered=invite_link.role_offered,
                max_uses=invite_link.max_uses,
                expires_at=invite_link.expires_at,
                deep_link=f"palateful://invite/{invite_link.token}",
            ),
            status=201,
        )

    class Params(BaseModel):
        resource_type: str
        resource_id: str
        role_offered: str
        max_uses: int | None = None
        expires_in_days: int | None = None

    class Response(BaseModel):
        id: str
        token: str
        resource_type: str
        resource_id: str
        role_offered: str
        max_uses: int | None
        expires_at: datetime | None
        deep_link: str
