"""Respond to meal event invitation endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.meal_event_participant import MealEventParticipant
from utils.models.user import User

VALID_RESPONSES = ["accepted", "declined", "maybe"]


class RespondToInvite(Endpoint):
    """Respond to a meal event invitation."""

    def execute(self, event_id: str, params: "RespondToInvite.Params"):
        """
        Respond to a meal event invitation.

        Args:
            event_id: The meal event's ID
            params: Response parameters

        Returns:
            Updated participant data
        """
        user: User = self.user

        # Validate response status
        if params.status not in VALID_RESPONSES:
            raise APIException(
                status_code=400,
                detail=f"Invalid response. Must be one of: {', '.join(VALID_RESPONSES)}",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Find meal event
        meal_event = self.database.find_by(MealEvent, id=event_id)
        if not meal_event:
            raise APIException(
                status_code=404,
                detail=f"Meal event with ID '{event_id}' not found",
                code=ErrorCode.MEAL_EVENT_NOT_FOUND,
            )

        # Find participant record for current user
        participant = self.database.find_by(
            MealEventParticipant, meal_event_id=event_id, user_id=user.id
        )
        if not participant:
            raise APIException(
                status_code=404,
                detail="You are not a participant of this event",
                code=ErrorCode.MEAL_EVENT_PARTICIPANT_NOT_FOUND,
            )

        # Update status
        participant.status = params.status
        self.database.db.commit()
        self.database.db.refresh(participant)

        return success(
            data=RespondToInvite.Response(
                user_id=str(user.id),
                user_email=user.email,
                user_name=user.name,
                status=participant.status,
                role=participant.role,
                assigned_tasks=participant.assigned_tasks or [],
                created_at=participant.created_at,
            )
        )

    class Params(BaseModel):
        status: str  # accepted | declined | maybe

    class Response(BaseModel):
        user_id: str
        user_email: str | None = None
        user_name: str | None = None
        status: str
        role: str
        assigned_tasks: list[str] = []
        created_at: datetime
