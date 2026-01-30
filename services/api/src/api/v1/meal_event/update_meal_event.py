"""Update meal event endpoint."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.meal_event_participant import MealEventParticipant
from utils.models.recipe import Recipe
from utils.models.user import User

VALID_STATUSES = ["planned", "shopping", "prepping", "cooking", "completed", "skipped"]
VALID_MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]


class UpdateMealEvent(Endpoint):
    """Update a meal event."""

    def execute(self, event_id: str, params: "UpdateMealEvent.Params"):
        """
        Update a meal event.

        Args:
            event_id: The meal event's ID
            params: Update parameters

        Returns:
            Updated meal event data
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
        participant = self.database.find_by(
            MealEventParticipant, meal_event_id=event_id, user_id=user.id
        )
        is_cohost = participant and participant.role in ("host", "cohost")
        if not is_owner and not is_cohost:
            raise APIException(
                status_code=403,
                detail="You don't have permission to update this meal event",
                code=ErrorCode.MEAL_EVENT_ACCESS_DENIED,
            )

        # Validate status if provided
        if params.status and params.status not in VALID_STATUSES:
            raise APIException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}",
                code=ErrorCode.MEAL_EVENT_INVALID_STATUS,
            )

        # Validate meal type if provided
        if params.meal_type and params.meal_type not in VALID_MEAL_TYPES:
            raise APIException(
                status_code=400,
                detail=f"Invalid meal type. Must be one of: {', '.join(VALID_MEAL_TYPES)}",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Verify recipe exists if updating
        if params.recipe_id:
            recipe = self.database.find_by(Recipe, id=params.recipe_id)
            if not recipe:
                raise APIException(
                    status_code=404,
                    detail=f"Recipe with ID '{params.recipe_id}' not found",
                    code=ErrorCode.RECIPE_NOT_FOUND,
                )

        # Update fields
        if params.title is not None:
            meal_event.title = params.title
        if params.description is not None:
            meal_event.description = params.description
        if params.scheduled_at is not None:
            meal_event.scheduled_at = params.scheduled_at
        if params.meal_type is not None:
            meal_event.meal_type = params.meal_type
        if params.status is not None:
            meal_event.status = params.status
        if params.recipe_id is not None:
            meal_event.recipe_id = params.recipe_id
        if params.pantry_id is not None:
            meal_event.pantry_id = params.pantry_id
        if params.notify_prep_start is not None:
            meal_event.notify_prep_start = params.notify_prep_start
        if params.prep_start_offset_minutes is not None:
            meal_event.prep_start_offset_minutes = params.prep_start_offset_minutes
        if params.notify_cook_start is not None:
            meal_event.notify_cook_start = params.notify_cook_start
        if params.cook_start_offset_minutes is not None:
            meal_event.cook_start_offset_minutes = params.cook_start_offset_minutes
        if params.is_shared is not None:
            meal_event.is_shared = params.is_shared
        if params.is_recurring is not None:
            meal_event.is_recurring = params.is_recurring
        if params.recurrence_rule is not None:
            meal_event.recurrence_rule = params.recurrence_rule
        if params.recurrence_end_date is not None:
            meal_event.recurrence_end_date = params.recurrence_end_date

        self.database.db.commit()
        self.database.db.refresh(meal_event)

        # Build recipe summary if present
        recipe_summary = None
        if meal_event.recipe:
            recipe_summary = UpdateMealEvent.RecipeSummary(
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
                UpdateMealEvent.ParticipantResponse(
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
            data=UpdateMealEvent.Response(
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

    class Params(BaseModel):
        title: str | None = None
        description: str | None = None
        scheduled_at: datetime | None = None
        meal_type: str | None = None
        status: str | None = None
        recipe_id: str | None = None
        pantry_id: str | None = None
        notify_prep_start: bool | None = None
        prep_start_offset_minutes: int | None = None
        notify_cook_start: bool | None = None
        cook_start_offset_minutes: int | None = None
        is_shared: bool | None = None
        is_recurring: bool | None = None
        recurrence_rule: str | None = None
        recurrence_end_date: date | None = None

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
        recipe: Optional["UpdateMealEvent.RecipeSummary"] = None
        pantry_id: str | None = None
        owner_id: str
        participants: list["UpdateMealEvent.ParticipantResponse"] = []
        created_at: datetime
        updated_at: datetime
