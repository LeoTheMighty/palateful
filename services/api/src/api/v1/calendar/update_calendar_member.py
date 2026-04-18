"""Update a calendar member — supports promote-to-owner with atomic caller demotion."""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.activity import Activity
from utils.models.calendar_user import CalendarUser
from utils.models.error_log import ErrorLog
from utils.models.user import User


class UpdateCalendarMember(Endpoint):
    """PATCH /calendars/{id}/members/{user_id}.

    Owner-only. The only supported role transition is `editor → owner`
    (promote target). The caller is atomically demoted to `editor` in
    the same transaction — i.e. ownership transfer.

    Direct demotion of the caller (`owner → editor` without a target
    being promoted) is rejected with `CALENDAR_OWNER_TRANSFER_REQUIRED`
    — otherwise the calendar would be ownerless.
    """

    def execute(self, calendar_id: str, target_user_id: str, params: "UpdateCalendarMember.Params"):
        user: User = self.user

        if params.role not in ("owner", "editor"):
            raise APIException(
                status_code=400,
                detail=f"Invalid role '{params.role}' — must be 'owner' or 'editor'",
                code=ErrorCode.CALENDAR_INVALID_ROLE,
            )

        # Caller must be an active owner.
        caller_row = self.database.find_by(
            CalendarUser,
            user_id=user.id,
            calendar_id=calendar_id,
        )
        if not caller_row or caller_row.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Calendar with ID '{calendar_id}' not found",
                code=ErrorCode.CALENDAR_NOT_FOUND,
            )
        if caller_row.role != "owner":
            raise APIException(
                status_code=403,
                detail="Only the calendar owner can change member roles",
                code=ErrorCode.CALENDAR_ACCESS_DENIED,
            )

        # Caller demoting themselves directly is blocked — must promote a target.
        if str(target_user_id) == str(user.id):
            raise APIException(
                status_code=400,
                detail=(
                    "Promote another member to owner instead — direct "
                    "self-demotion would leave the calendar ownerless"
                ),
                code=ErrorCode.CALENDAR_OWNER_TRANSFER_REQUIRED,
            )

        # Target must be an active member.
        target_row = self.database.find_by(
            CalendarUser,
            user_id=target_user_id,
            calendar_id=calendar_id,
        )
        if not target_row or target_row.archived_at is not None:
            raise APIException(
                status_code=404,
                detail="Member not found on this calendar",
                code=ErrorCode.CALENDAR_NOT_FOUND,
            )

        # Only `editor → owner` is supported. Setting target to its current role
        # is a no-op success; setting to a role that doesn't transition cleanly
        # gets the same transfer-required error.
        if params.role == target_row.role:
            return success(data=UpdateCalendarMember.Response(
                user_id=str(target_row.user_id),
                role=target_row.role,
            ))

        if params.role != "owner":
            raise APIException(
                status_code=400,
                detail=(
                    "Only `editor → owner` is supported — to demote yourself, "
                    "promote another member to owner (you'll be demoted automatically)"
                ),
                code=ErrorCode.CALENDAR_OWNER_TRANSFER_REQUIRED,
            )

        # Ownership transfer: row-level lock both rows, flip both roles,
        # let the DB partial unique index catch any race that slips past.
        db = self.db
        try:
            # Re-fetch with FOR UPDATE so concurrent transfers serialize.
            db.query(CalendarUser).filter(
                CalendarUser.calendar_id == calendar_id,
                CalendarUser.user_id == user.id,
                CalendarUser.archived_at.is_(None),
            ).with_for_update().first()
            db.query(CalendarUser).filter(
                CalendarUser.calendar_id == calendar_id,
                CalendarUser.user_id == target_user_id,
                CalendarUser.archived_at.is_(None),
            ).with_for_update().first()

            # Demote caller first to keep the partial unique index satisfied
            # at every intermediate state.
            caller_row.role = "editor"
            db.add(caller_row)
            db.flush()
            target_row.role = "owner"
            db.add(target_row)
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise APIException(
                status_code=409,
                detail="Another ownership transfer raced with this one — please refresh",
                code=ErrorCode.CALENDAR_OWNER_TRANSFER_CONFLICT,
            ) from exc

        # Activity log
        db.add(Activity(
            user_id=user.id,
            action="ownership_transferred",
            resource_type="calendar",
            resource_id=calendar_id,
            target_type="user",
            target_id=target_user_id,
            details={
                "previous_owner_id": str(user.id),
                "new_owner_id": str(target_user_id),
            },
        ))

        # Audit log — service="audit" keeps it out of api-error dashboards.
        self.database.create(ErrorLog(
            error_type="CalendarMemberAudit",
            error_message=(
                f"Ownership of calendar {calendar_id} transferred "
                f"from {user.id} to {target_user_id}"
            ),
            service="audit",
            user_id=user.id,
        ))

        db.commit()

        return success(data=UpdateCalendarMember.Response(
            user_id=str(target_user_id),
            role="owner",
            transferred_at=datetime.now(UTC),
        ))

    class Params(BaseModel):
        role: str

    class Response(BaseModel):
        user_id: str
        role: str
        transferred_at: datetime | None = None
