"""Meal event endpoints router."""

from datetime import date

from api.v1.meal_event import (
    AddMealEventToShoppingList,
    CreateMealEvent,
    DeleteMealEvent,
    GetMealEvent,
    InviteParticipant,
    ListMealEvents,
    RespondToInvite,
    SkipMealEvent,
    UpdateMealEvent,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.database import Database

meal_event_router = APIRouter(tags=["meal-events"])


@meal_event_router.get("/meal-events")
async def list_meal_events(
    limit: int = 20,
    offset: int = 0,
    start_date: date | None = None,
    end_date: date | None = None,
    meal_type: str | None = None,
    status: str | None = None,
    calendar_id: str | None = None,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List meal events for the current user."""
    return ListMealEvents.call(
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
        meal_type=meal_type,
        status=status,
        calendar_id=calendar_id,
        user=user,
        database=database,
    )


@meal_event_router.post("/meal-events")
async def create_meal_event(
    params: CreateMealEvent.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Create a new meal event."""
    return CreateMealEvent.call(
        params=params,
        user=user,
        database=database,
    )


@meal_event_router.get("/meal-events/{event_id}")
async def get_meal_event(
    event_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get meal event details."""
    return GetMealEvent.call(
        event_id=event_id,
        user=user,
        database=database,
    )


@meal_event_router.put("/meal-events/{event_id}")
async def update_meal_event(
    event_id: str,
    params: UpdateMealEvent.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Update a meal event."""
    return UpdateMealEvent.call(
        event_id=event_id,
        params=params,
        user=user,
        database=database,
    )


@meal_event_router.delete("/meal-events/{event_id}")
async def delete_meal_event(
    event_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Delete a meal event."""
    return DeleteMealEvent.call(
        event_id=event_id,
        user=user,
        database=database,
    )


@meal_event_router.post("/meal-events/{event_id}/skip")
async def skip_meal_event(
    event_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Skip a meal event (dismiss notifications)."""
    return SkipMealEvent.call(
        event_id=event_id,
        user=user,
        database=database,
    )


@meal_event_router.post("/meal-events/{event_id}/invite")
async def invite_participant(
    event_id: str,
    params: InviteParticipant.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Invite a participant to a meal event."""
    return InviteParticipant.call(
        event_id=event_id,
        params=params,
        user=user,
        database=database,
    )


@meal_event_router.post("/meal-events/{event_id}/respond")
async def respond_to_invite(
    event_id: str,
    params: RespondToInvite.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Respond to a meal event invitation."""
    return RespondToInvite.call(
        event_id=event_id,
        params=params,
        user=user,
        database=database,
    )


@meal_event_router.post("/meal-events/{event_id}/add-to-shopping-list")
async def add_meal_event_to_shopping_list(
    event_id: str,
    params: AddMealEventToShoppingList.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Append a single calendar event's ingredients to a shopping list (mcal-5).

    Replaces the now-deleted PopulateFromCalendar's per-event behavior.
    Recipe-linked events expand via the recipe's ingredient rows; Meal-
    linked events expand via `aggregate_meal_ingredients` with sum-
    within-meal dedupe.
    """
    return AddMealEventToShoppingList.call(
        event_id=event_id,
        params=params,
        user=user,
        database=database,
    )
