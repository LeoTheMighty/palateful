"""Invite participant to meal event endpoint."""

from datetime import datetime

from api.v1.meal_event.utils.notifications import notify_meal_event_invite
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.meal_event_participant import MealEventParticipant
from utils.models.user import User


class InviteParticipant(Endpoint):
    """Invite a participant to a meal event."""

    def execute(self, event_id: str, params: "InviteParticipant.Params"):
        """
        Invite a participant to a meal event.

        Args:
            event_id: The meal event's ID
            params: Invitation parameters

        Returns:
            Participant data
        """
        user: User = self.user

        # Find meal event
        meal_event = self.database.find_by(MealEvent, id=event_id)
        if not meal_event:
            raise APIException(
                status_code=404,
                detail=f"Meal event with ID '{event_id}' not found",
                code=ErrorCode.MEAL_EVENT_NOT_FOUND,
            )

        # Check access - must be owner or cohost
        is_owner = meal_event.owner_id == user.id
        current_participant = self.database.find_by(
            MealEventParticipant, meal_event_id=event_id, user_id=user.id
        )
        is_cohost = current_participant and current_participant.role in ("host", "cohost")
        if not is_owner and not is_cohost:
            raise APIException(
                status_code=403,
                detail="You don't have permission to invite participants to this event",
                code=ErrorCode.MEAL_EVENT_ACCESS_DENIED,
            )

        # Find the user to invite
        invited_user = None
        if params.user_id:
            invited_user = self.database.find_by(User, id=params.user_id)
        elif params.email:
            invited_user = self.database.find_by(User, email=params.email)

        if not invited_user:
            raise APIException(
                status_code=404,
                detail="User not found",
                code=ErrorCode.USER_NOT_FOUND,
            )

        # Check if already a participant
        existing = self.database.find_by(
            MealEventParticipant, meal_event_id=event_id, user_id=invited_user.id
        )
        if existing:
            raise APIException(
                status_code=400,
                detail="User is already a participant of this event",
                code=ErrorCode.MEAL_EVENT_ALREADY_PARTICIPANT,
            )

        # Create participant
        participant = MealEventParticipant(
            meal_event_id=meal_event.id,
            user_id=invited_user.id,
            status="invited",
            role=params.role,
            assigned_tasks=[],
        )
        self.database.create(participant)
        self.database.db.refresh(participant)

        # Mark event as shared
        if not meal_event.is_shared:
            meal_event.is_shared = True
            self.database.db.commit()

        # Send notification to invited user
        notify_meal_event_invite(meal_event, invited_user, user, params.message)

        return success(
            data=InviteParticipant.Response(
                user_id=str(invited_user.id),
                user_email=invited_user.email,
                user_name=invited_user.name,
                status=participant.status,
                role=participant.role,
                assigned_tasks=participant.assigned_tasks or [],
                created_at=participant.created_at,
            ),
            status=201,
        )

    class Params(BaseModel):
        user_id: str | None = None
        email: str | None = None
        role: str = "guest"
        message: str | None = None  # For notification

    class Response(BaseModel):
        user_id: str
        user_email: str | None = None
        user_name: str | None = None
        status: str
        role: str
        assigned_tasks: list[str] = []
        created_at: datetime
