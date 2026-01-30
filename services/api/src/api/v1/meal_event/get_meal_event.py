"""Get meal event endpoint."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.meal_event_participant import MealEventParticipant
from utils.models.user import User


class GetMealEvent(Endpoint):
    """Get a meal event by ID."""

    def execute(self, event_id: str):
        """
        Get a meal event by ID.

        Args:
            event_id: The meal event's ID

        Returns:
            Meal event data
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

        # Check access - must be owner or participant
        is_owner = meal_event.owner_id == user.id
        participant = self.database.find_by(
            MealEventParticipant, meal_event_id=event_id, user_id=user.id
        )
        if not is_owner and not participant:
            raise APIException(
                status_code=403,
                detail="You don't have access to this meal event",
                code=ErrorCode.MEAL_EVENT_ACCESS_DENIED,
            )

        # Build recipe summary if present
        recipe_summary = None
        if meal_event.recipe:
            recipe_summary = GetMealEvent.RecipeSummary(
                id=str(meal_event.recipe.id),
                name=meal_event.recipe.name,
                description=meal_event.recipe.description,
                prep_time=meal_event.recipe.prep_time,
                cook_time=meal_event.recipe.cook_time,
                image_url=meal_event.recipe.image_url,
            )

        # Build participants list
        participants = []
        for p in meal_event.participants:
            participants.append(
                GetMealEvent.ParticipantResponse(
                    user_id=str(p.user_id),
                    user_email=p.user.email if p.user else None,
                    user_name=p.user.name if p.user else None,
                    status=p.status,
                    role=p.role,
                    assigned_tasks=p.assigned_tasks or [],
                    created_at=p.created_at,
                )
            )

        return success(
            data=GetMealEvent.Response(
                id=str(meal_event.id),
                title=meal_event.title,
                description=meal_event.description,
                scheduled_at=meal_event.scheduled_at,
                meal_type=meal_event.meal_type,
                status=meal_event.status,
                notify_prep_start=meal_event.notify_prep_start,
                prep_start_offset_minutes=meal_event.prep_start_offset_minutes,
                notify_cook_start=meal_event.notify_cook_start,
                cook_start_offset_minutes=meal_event.cook_start_offset_minutes,
                is_shared=meal_event.is_shared,
                is_recurring=meal_event.is_recurring,
                recurrence_rule=meal_event.recurrence_rule,
                recurrence_end_date=meal_event.recurrence_end_date,
                parent_event_id=(
                    str(meal_event.parent_event_id)
                    if meal_event.parent_event_id
                    else None
                ),
                recipe=recipe_summary,
                pantry_id=str(meal_event.pantry_id) if meal_event.pantry_id else None,
                owner_id=str(meal_event.owner_id),
                participants=participants,
                created_at=meal_event.created_at,
                updated_at=meal_event.updated_at,
            )
        )

    class RecipeSummary(BaseModel):
        id: str
        name: str
        description: str | None = None
        prep_time: int | None = None
        cook_time: int | None = None
        image_url: str | None = None

    class ParticipantResponse(BaseModel):
        user_id: str
        user_email: str | None = None
        user_name: str | None = None
        status: str
        role: str
        assigned_tasks: list[str] = []
        created_at: datetime

    class Response(BaseModel):
        id: str
        title: str
        description: str | None = None
        scheduled_at: datetime
        meal_type: str
        status: str
        notify_prep_start: bool
        prep_start_offset_minutes: int
        notify_cook_start: bool
        cook_start_offset_minutes: int
        is_shared: bool
        is_recurring: bool
        recurrence_rule: str | None = None
        recurrence_end_date: date | None = None
        parent_event_id: str | None = None
        recipe: Optional["GetMealEvent.RecipeSummary"] = None
        pantry_id: str | None = None
        owner_id: str
        participants: list["GetMealEvent.ParticipantResponse"] = []
        created_at: datetime
        updated_at: datetime
