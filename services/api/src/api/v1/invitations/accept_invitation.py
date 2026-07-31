"""Accept invitation endpoint."""

from datetime import UTC, datetime

from api.v1.invitations.helpers import (
    create_membership,
    get_resource_name,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.activity import Activity
from utils.models.invitation import Invitation
from utils.models.user import User
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)


class AcceptInvitation(AsyncEndpoint):
    """Accept a received invitation."""

    async def execute(self, invitation_id: str):
        user: User = self.user

        result = await self.db.execute(
            select(Invitation)
            .options(joinedload(Invitation.from_user))
            .where(Invitation.id == invitation_id)
        )
        invitation = result.scalar_one_or_none()

        if not invitation:
            raise APIException(
                status_code=404,
                detail="Invitation not found",
                code=ErrorCode.INVITATION_NOT_FOUND,
            )

        # Verify recipient
        if invitation.to_user_id != user.id:
            raise APIException(
                status_code=403,
                detail="You can only accept invitations sent to you",
                code=ErrorCode.INVITATION_ACCESS_DENIED,
            )

        # Verify pending
        if invitation.status != "pending":
            raise APIException(
                status_code=400,
                detail=f"This invitation has already been {invitation.status}",
                code=ErrorCode.INVITATION_NOT_PENDING,
            )

        # Check expiration
        if invitation.expires_at and invitation.expires_at < datetime.now(UTC):
            invitation.status = "expired"
            await self.db.commit()
            raise APIException(
                status_code=410,
                detail="This invitation has expired",
                code=ErrorCode.INVITATION_EXPIRED,
            )

        # Create membership (idempotent)
        await create_membership(
            self.db,
            user_id=user.id,
            resource_type=invitation.resource_type,
            resource_id=invitation.resource_id,
            role=invitation.role_offered,
            invited_by_id=invitation.from_user_id,
        )

        # Update invitation status
        invitation.status = "accepted"
        invitation.responded_at = datetime.now(UTC)

        # Activity log
        self.db.add(Activity(
            user_id=user.id,
            action="joined",
            resource_type=invitation.resource_type,
            resource_id=invitation.resource_id,
            details={
                "via": "invitation",
                "invitation_id": str(invitation.id),
                "role": invitation.role_offered,
            },
        ))

        await self.db.commit()

        # Notify inviter
        from_user = invitation.from_user
        resource_name = await get_resource_name(
            self.db, invitation.resource_type, invitation.resource_id
        )
        display_name = (
            f"@{user.username}" if user.username else user.name or "Someone"
        )
        # Wrap the sync Firebase call in a threadpool so the event
        # loop isn't blocked on FCM latency (equivalent to the aam-8
        # `send_to_user_async` variant).
        # Fresh sync Database is created inside the push service when
        # `db_session` is omitted (can't share the async session across
        # the threadpool boundary).
        push_service = get_push_service()
        await run_in_threadpool(
            push_service.send_to_user,
            from_user,
            PushNotification(
                title="Invitation Accepted",
                body=f"{display_name} joined {resource_name or invitation.resource_type}",
                notification_type=NotificationType.INVITATION_ACCEPTED,
                data={
                    "invitation_id": str(invitation.id),
                    "resource_type": invitation.resource_type,
                    "resource_id": str(invitation.resource_id),
                    "resource_name": resource_name or "",
                    "user_id": str(user.id),
                },
            ),
        )

        return success(
            data=AcceptInvitation.Response(
                id=str(invitation.id),
                resource_type=invitation.resource_type,
                resource_id=str(invitation.resource_id),
                role=invitation.role_offered,
                status="accepted",
            )
        )

    class Response(BaseModel):
        id: str
        resource_type: str
        resource_id: str
        role: str
        status: str
