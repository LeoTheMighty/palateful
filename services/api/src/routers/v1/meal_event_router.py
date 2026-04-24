"""Meal event endpoints router."""

import logging
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
from api.v1.meal_event.utils.notifications import notify_meal_event_invite_accepted
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.meal_event import MealEvent
from utils.models.user import User
from utils.services.database import Database

logger = logging.getLogger(__name__)

meal_event_router = APIRouter(tags=["meal-events"])


@meal_event_router.get("/meal-events")
def list_meal_events(
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
def create_meal_event(
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
def get_meal_event(
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
def update_meal_event(
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
def delete_meal_event(
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
def skip_meal_event(
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
def invite_participant(
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
def respond_to_invite(
    event_id: str,
    params: RespondToInvite.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Respond to a meal event invitation."""
    # Use `run()` so the back-fan branch sees the raw dict; the final
    # response shape is built via `handle_result()` below.
    endpoint = RespondToInvite(
        event_id=event_id,
        params=params,
        user=user,
        database=database,
    )
    result = endpoint.run()

    # partner-4: back-fan the RSVP status to the event owner.
    if result.get("success"):
        meal_event = database.find_by(MealEvent, id=event_id)
        if meal_event is not None:  # pragma: no branch — defensive; success path implies event exists
            try:
                notify_meal_event_invite_accepted(
                    meal_event=meal_event,
                    responder=user,
                    status=params.status,
                    database=database,
                )
            except Exception as exc:  # noqa: BLE001 — never fail the RSVP  # pragma: no cover — best-effort notify
                logger.error(
                    "meal_event_rsvp: back-fan notify failed event_id=%s err=%s: %s",
                    event_id, type(exc).__name__, exc,
                )

    return RespondToInvite.handle_result(result)


@meal_event_router.post("/meal-events/{event_id}/add-to-shopping-list")
def add_meal_event_to_shopping_list(
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
