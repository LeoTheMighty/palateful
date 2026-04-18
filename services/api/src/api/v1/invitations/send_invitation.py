"""Send invitation endpoint."""

from datetime import UTC, datetime, timedelta

from api.v1.invitations.helpers import (
    check_existing_membership,
    check_resource_permission,
    get_resource_name,
    validate_resource_and_role,
)
from pydantic import BaseModel
from sqlalchemy import func, select
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.invitation import Invitation
from utils.models.user import User
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)

MAX_INVITATIONS_PER_DAY = 30


class SendInvitation(Endpoint):
    """Send an invitation to share a resource."""

    def execute(self, params: "SendInvitation.Params"):
        user: User = self.user

        # Validate resource type and role
        validate_resource_and_role(params.resource_type, params.role_offered)

        # Check inviter has permission on the resource
        check_resource_permission(
            self.db, user.id, params.resource_type, params.resource_id
        )

        # Resolve target user
        target_user = None
        to_email = None

        if params.to_user_id:
            target_user = self.db.execute(
                select(User).where(User.id == params.to_user_id)
            ).scalar_one_or_none()
            if not target_user:
                raise APIException(
                    status_code=404,
                    detail="User not found",
                    code=ErrorCode.USER_NOT_FOUND,
                )

        elif params.to_username:
            username = params.to_username.lower().strip()
            if username.startswith("@"):
                username = username[1:]
            target_user = self.db.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()
            if not target_user:
                raise APIException(
                    status_code=404,
                    detail=f"User @{username} not found",
                    code=ErrorCode.USER_NOT_FOUND,
                )

        elif params.to_email:
            to_email = params.to_email.lower().strip()
            # Check if a user with this email exists
            target_user = self.db.execute(
                select(User).where(func.lower(User.email) == to_email)
            ).scalar_one_or_none()

        else:
            raise APIException(
                status_code=400,
                detail="One of to_user_id, to_username, or to_email is required",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # Can't invite yourself
        if target_user and target_user.id == user.id:
            raise APIException(
                status_code=400,
                detail="You cannot invite yourself",
                code=ErrorCode.INVITATION_SELF_INVITE,
            )

        # Check if target is already a member
        if target_user and check_existing_membership(
            self.db, target_user.id, params.resource_type, params.resource_id
        ):
            raise APIException(
                status_code=409,
                detail="This user is already a member",
                code=ErrorCode.INVITATION_ALREADY_MEMBER,
            )

        # Check for existing pending invitation
        dup_query = select(Invitation).where(
            Invitation.resource_type == params.resource_type,
            Invitation.resource_id == params.resource_id,
            Invitation.status == "pending",
            Invitation.archived_at.is_(None),
        )
        if target_user:
            dup_query = dup_query.where(Invitation.to_user_id == target_user.id)
        elif to_email:
            dup_query = dup_query.where(
                func.lower(Invitation.to_email) == to_email
            )
        else:  # pragma: no cover — validation above ensures target_user or to_email is set
            pass

        existing = self.db.execute(dup_query).scalar_one_or_none()
        if existing:
            raise APIException(
                status_code=409,
                detail="An invitation has already been sent",
                code=ErrorCode.INVITATION_ALREADY_SENT,
            )

        # Rate limit
        day_ago = datetime.now(UTC) - timedelta(days=1)
        sent_today = self.db.execute(
            select(func.count(Invitation.id)).where(
                Invitation.from_user_id == user.id,
                Invitation.created_at >= day_ago,
            )
        ).scalar()
        if sent_today >= MAX_INVITATIONS_PER_DAY:
            raise APIException(
                status_code=429,
                detail=f"You can only send {MAX_INVITATIONS_PER_DAY} invitations per day",
                code=ErrorCode.RATE_LIMITED,
            )

        # Create invitation
        invitation = Invitation(
            from_user_id=user.id,
            to_user_id=target_user.id if target_user else None,
            to_email=to_email if not target_user else None,
            resource_type=params.resource_type,
            resource_id=params.resource_id,
            role_offered=params.role_offered,
            status="pending",
            message=params.message,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        self.db.add(invitation)
        self.db.commit()
        self.db.refresh(invitation)

        # Send push notification if target user exists
        if target_user:
            resource_name = get_resource_name(
                self.db, params.resource_type, params.resource_id
            )
            display_name = (
                f"@{user.username}" if user.username else user.name or "Someone"
            )
            push_service = get_push_service()
            push_service.send_to_user(
                target_user,
                PushNotification(
                    title="Invitation Received",
                    body=f"{display_name} invited you to {resource_name or params.resource_type}",
                    notification_type=NotificationType.INVITATION_RECEIVED,
                    data={
                        "invitation_id": str(invitation.id),
                        "resource_type": params.resource_type,
                        "resource_id": str(params.resource_id),
                        "resource_name": resource_name or "",
                    },
                ),
                db_session=self.db,
            )

        return success(
            data=SendInvitation.Response(
                id=str(invitation.id),
                resource_type=invitation.resource_type,
                resource_id=str(invitation.resource_id),
                role_offered=invitation.role_offered,
                status=invitation.status,
                to_user_id=str(target_user.id) if target_user else None,
                to_email=invitation.to_email,
                expires_at=invitation.expires_at,
            ),
            status=201,
        )

    class Params(BaseModel):
        resource_type: str
        resource_id: str
        role_offered: str
        to_user_id: str | None = None
        to_username: str | None = None
        to_email: str | None = None
        message: str | None = None

    class Response(BaseModel):
        id: str
        resource_type: str
        resource_id: str
        role_offered: str
        status: str
        to_user_id: str | None = None
        to_email: str | None = None
        expires_at: datetime | None = None
