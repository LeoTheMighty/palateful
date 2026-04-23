"""Join via invite link endpoint."""

from datetime import UTC, datetime

from api.v1.invitations.helpers import (
    check_existing_membership,
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
from utils.models.invite_link import InviteLink
from utils.models.user import User
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)


class JoinViaLink(AsyncEndpoint):
    """Join a resource via an invite link token."""

    async def execute(self, token: str):
        user: User = self.user

        result = await self.db.execute(
            select(InviteLink)
            .options(joinedload(InviteLink.created_by))
            .where(
                InviteLink.token == token,
                InviteLink.archived_at.is_(None),
            )
        )
        invite_link = result.scalar_one_or_none()

        if not invite_link:
            raise APIException(
                status_code=404,
                detail="Invite link not found",
                code=ErrorCode.INVITE_LINK_NOT_FOUND,
            )

        # Validate link state
        now = datetime.now(UTC)

        if not invite_link.is_active:
            raise APIException(
                status_code=410,
                detail="This invite link has been deactivated",
                code=ErrorCode.INVITE_LINK_INACTIVE,
            )

        if invite_link.expires_at and invite_link.expires_at < now:
            raise APIException(
                status_code=410,
                detail="This invite link has expired",
                code=ErrorCode.INVITE_LINK_EXPIRED,
            )

        if invite_link.max_uses and invite_link.use_count >= invite_link.max_uses:
            raise APIException(
                status_code=410,
                detail="This invite link has reached its usage limit",
                code=ErrorCode.INVITE_LINK_MAX_USES_REACHED,
            )

        # Already a member — succeed silently
        if await check_existing_membership(
            self.db, user.id, invite_link.resource_type, invite_link.resource_id
        ):
            resource_name = await get_resource_name(
                self.db, invite_link.resource_type, invite_link.resource_id
            )
            return success(
                data=JoinViaLink.Response(
                    resource_type=invite_link.resource_type,
                    resource_id=str(invite_link.resource_id),
                    resource_name=resource_name,
                    role=invite_link.role_offered,
                    already_member=True,
                )
            )

        # Create membership
        await create_membership(
            self.db,
            user_id=user.id,
            resource_type=invite_link.resource_type,
            resource_id=invite_link.resource_id,
            role=invite_link.role_offered,
            invited_by_id=invite_link.created_by_id,
        )

        # Increment use count
        invite_link.use_count += 1

        # Activity log
        self.db.add(Activity(
            user_id=user.id,
            action="joined",
            resource_type=invite_link.resource_type,
            resource_id=invite_link.resource_id,
            details={
                "via": "invite_link",
                "invite_link_id": str(invite_link.id),
                "role": invite_link.role_offered,
            },
        ))

        await self.db.commit()

        # Notify link creator
        resource_name = await get_resource_name(
            self.db, invite_link.resource_type, invite_link.resource_id
        )
        display_name = (
            f"@{user.username}" if user.username else user.name or "Someone"
        )
        creator = invite_link.created_by
        # aam-8 hasn't landed — `push_service.send_to_user` still talks
        # to sync Firebase Admin + sync Database. Wrap in threadpool so
        # the async event loop isn't blocked on the FCM round-trip.
        push_service = get_push_service()
        await run_in_threadpool(
            push_service.send_to_user,
            creator,
            PushNotification(
                title="New Member",
                body=f"{display_name} joined {resource_name or invite_link.resource_type} via your link",
                notification_type=NotificationType.MEMBER_JOINED,
                data={
                    "resource_type": invite_link.resource_type,
                    "resource_id": str(invite_link.resource_id),
                    "user_id": str(user.id),
                },
            ),
            # Note: `db_session` intentionally omitted — threadpool
            # task can't share the async session. The push service
            # falls back to a fresh sync Database() when needed.
        )

        return success(
            data=JoinViaLink.Response(
                resource_type=invite_link.resource_type,
                resource_id=str(invite_link.resource_id),
                resource_name=resource_name,
                role=invite_link.role_offered,
                already_member=False,
            )
        )

    class Response(BaseModel):
        resource_type: str
        resource_id: str
        resource_name: str | None
        role: str
        already_member: bool
