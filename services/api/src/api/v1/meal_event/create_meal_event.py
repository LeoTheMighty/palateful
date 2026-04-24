"""Create meal event endpoint."""

from datetime import date, datetime, time
from typing import Optional

from api.v1.calendar.dependencies import require_calendar_access_async
from api.v1.meal_event._meal_binding import (
    MealSummary,
    build_meal_summary,
    require_meal_available_async,
    validate_recipe_meal_xor,
)
from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.meal_event_participant import MealEventParticipant
from utils.models.recipe import Recipe
from utils.models.user import User


class CreateMealEvent(AsyncEndpoint):
    """Create a new meal event."""

    async def execute(self, params: "CreateMealEvent.Params"):
        """Create a new meal event on the calendar."""
        user: User = self.user

        # Explicit empty-string / null check maps to the calendar-required
        # error code. FastAPI already 422s on a totally missing key, but
        # older clients that send calendar_id="" get a clear 400 instead
        # of a 500 later.
        if not params.calendar_id:
            raise APIException(
                status_code=400,
                detail="calendar_id is required",
                code=ErrorCode.MEAL_EVENT_CALENDAR_REQUIRED,
            )

        # Verify membership + write role on the target calendar.
        await require_calendar_access_async(
            params.calendar_id, user, self.database
        )

        # XOR gate before any DB write.
        validate_recipe_meal_xor(params.recipe_id, params.meal_id)

        # Verify recipe exists if provided
        recipe = None
        if params.recipe_id:
            recipe = await self.database.find_by(Recipe, id=params.recipe_id)
            if not recipe:
                raise APIException(
                    status_code=404,
                    detail=f"Recipe with ID '{params.recipe_id}' not found",
                    code=ErrorCode.RECIPE_NOT_FOUND,
                )

        # Verify meal exists + user can read its book + it isn't archived.
        meal = None
        if params.meal_id:
            meal = await require_meal_available_async(
                self.database.db, params.meal_id, user
            )

        # Create meal event
        meal_event = MealEvent(
            title=params.title,
            description=params.description,
            scheduled_at=params.scheduled_at,
            meal_type=params.meal_type,
            recipe_id=params.recipe_id,
            meal_id=params.meal_id,
            pantry_id=params.pantry_id,
            owner_id=user.id,
            calendar_id=params.calendar_id,
            notify_prep_start=params.notify_prep_start,
            prep_start_offset_minutes=params.prep_start_offset_minutes,
            notify_cook_start=params.notify_cook_start,
            cook_start_offset_minutes=params.cook_start_offset_minutes,
            meal_reminder_time=params.meal_reminder_time,
            is_shared=params.is_shared,
            is_recurring=params.is_recurring,
            recurrence_rule=params.recurrence_rule,
            recurrence_end_date=params.recurrence_end_date,
        )
        await self.database.create(meal_event)
        await self.database.db.refresh(meal_event)

        # Add owner as host participant
        participant = MealEventParticipant(
            meal_event_id=meal_event.id,
            user_id=user.id,
            status="accepted",
            role="host",
        )
        await self.database.create(participant)

        # Build recipe summary if present
        recipe_summary = None
        if recipe:
            recipe_summary = CreateMealEvent.RecipeSummary(
                id=str(recipe.id),
                name=recipe.name,
                description=recipe.description,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                image_url=recipe.image_url,
            )

        meal_summary = build_meal_summary(meal) if meal else None

        return success(
            data=CreateMealEvent.Response(
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
                meal_reminder_time=meal_event.meal_reminder_time,
                reminder_time=meal_event.reminder_time,
                is_shared=meal_event.is_shared,
                is_recurring=meal_event.is_recurring,
                recurrence_rule=meal_event.recurrence_rule,
                recurrence_end_date=meal_event.recurrence_end_date,
                recipe=recipe_summary,
                meal_id=str(meal_event.meal_id) if meal_event.meal_id else None,
                meal_summary=meal_summary,
                pantry_id=str(meal_event.pantry_id) if meal_event.pantry_id else None,
                owner_id=str(meal_event.owner_id),
                calendar_id=str(meal_event.calendar_id),
                participants=[
                    CreateMealEvent.ParticipantResponse(
                        user_id=str(user.id),
                        user_email=user.email,
                        user_name=user.name,
                        status="accepted",
                        role="host",
                        assigned_tasks=[],
                        created_at=participant.created_at,
                    )
                ],
                created_at=meal_event.created_at,
                updated_at=meal_event.updated_at,
            ),
            status=201,
        )

    class Params(BaseModel):
        title: str
        description: str | None = None
        scheduled_at: datetime
        meal_type: str  # breakfast | lunch | dinner | snack
        calendar_id: str | None = None
        recipe_id: str | None = None
        meal_id: str | None = None
        pantry_id: str | None = None
        notify_prep_start: bool = True
        prep_start_offset_minutes: int = 60
        notify_cook_start: bool = True
        cook_start_offset_minutes: int = 30
        meal_reminder_time: time | None = None
        is_shared: bool = False
        is_recurring: bool = False
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
        meal_reminder_time: time | None = None
        reminder_time: time
        is_shared: bool
        is_recurring: bool
        recurrence_rule: str | None = None
        recurrence_end_date: date | None = None
        recipe: Optional["CreateMealEvent.RecipeSummary"] = None
        meal_id: str | None = None
        meal_summary: MealSummary | None = None
        pantry_id: str | None = None
        owner_id: str
        calendar_id: str
        participants: list["CreateMealEvent.ParticipantResponse"] = []
        created_at: datetime
        updated_at: datetime
