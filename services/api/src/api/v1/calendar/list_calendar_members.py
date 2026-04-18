"""List calendar members (active + pending invites)."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.calendar_user import CalendarUser
from utils.models.invitation import Invitation
from utils.models.user import User


class ListCalendarMembers(Endpoint):
    """Return active members + pending calendar invitations.

    Read-only — owner OR editor can call. Non-members 404 (matches
    `get_calendar` existence-leak guard).
    """

    def execute(self, calendar_id: str):
        user: User = self.user

        membership = self.database.find_by(
            CalendarUser,
            user_id=user.id,
            calendar_id=calendar_id,
        )
        if not membership or membership.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Calendar with ID '{calendar_id}' not found",
                code=ErrorCode.CALENDAR_NOT_FOUND,
            )

        active_rows = (
            self.db.query(CalendarUser, User)
            .join(User, CalendarUser.user_id == User.id)
            .filter(
                CalendarUser.calendar_id == calendar_id,
                CalendarUser.archived_at.is_(None),
            )
            .all()
        )
        members = [
            ListCalendarMembers.MemberItem(
                user_id=str(cu.user_id),
                name=u.name,
                email=u.email,
                role=cu.role,
                status="active",
                invited_by_id=str(cu.invited_by_id) if cu.invited_by_id else None,
                created_at=cu.created_at,
            )
            for cu, u in active_rows
        ]

        pending = self.db.execute(
            select(Invitation).where(
                Invitation.resource_type == "calendar",
                Invitation.resource_id == calendar_id,
                Invitation.status == "pending",
                Invitation.archived_at.is_(None),
            )
        ).scalars().all()

        for inv in pending:
            members.append(
                ListCalendarMembers.MemberItem(
                    user_id=str(inv.to_user_id) if inv.to_user_id else None,
                    name=None,
                    email=inv.to_email,
                    role=inv.role_offered,
                    status="pending",
                    invited_by_id=str(inv.from_user_id),
                    created_at=inv.created_at,
                    invitation_id=str(inv.id),
                )
            )

        return success(data=ListCalendarMembers.Response(members=members))

    class MemberItem(BaseModel):
        user_id: str | None
        name: str | None = None
        email: str | None = None
        role: str
        status: str
        invited_by_id: str | None = None
        created_at: datetime
        invitation_id: str | None = None

    class Response(BaseModel):
        members: list["ListCalendarMembers.MemberItem"]
