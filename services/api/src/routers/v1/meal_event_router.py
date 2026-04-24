"""Meal event endpoints router.

aam-14: flipped to `get_async_database` + `get_current_user_async`.
Every endpoint dispatches through `await Foo.call(...)` on an
`AsyncEndpoint` subclass. The `/respond` route's back-fan notification
re-uses `RespondToInvite.run()` to branch on the raw success dict
before wrapping the response (same pattern as the sync version),
and dispatches the sync `notify_meal_event_invite_accepted` via
`notify_via_threadpool`.
"""

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
from api.v1.meal_event.utils.notifications import (
    notify_meal_event_invite_accepted,
)
from dependencies import get_async_database, get_current_user_async
from fastapi import APIRouter, Depends
from utils.models.meal_event import MealEvent
from utils.models.user import User
from utils.services.async_database import AsyncDatabase
from utils.services.notifications_bridge import notify_via_threadpool

logger = logging.getLogger(__name__)

meal_event_router = APIRouter(tags=["meal-events"])


def _notify_rsvp_on_threadpool(
    meal_event_id: str,
    responder_id: str,
    status: str,
    *,
    database,
) -> None:
    """Threadpool-side re-fetch + fan-out for the RSVP back-fan.

    The sync `notify_meal_event_invite_accepted` takes `database: Database`;
    `notify_via_threadpool` injects a fresh sync session, and we re-fetch
    the event + responder on it before calling the helper.
    """
    meal_event = database.find_by(MealEvent, id=meal_event_id)
    responder = database.find_by(User, id=responder_id)
    if meal_event is None or responder is None:
        return
    notify_meal_event_invite_accepted(
        meal_event=meal_event,
        responder=responder,
        status=status,
        database=database,
    )


@meal_event_router.get("/meal-events")
async def list_meal_events(
    limit: int = 20,
    offset: int = 0,
    start_date: date | None = None,
    end_date: date | None = None,
    meal_type: str | None = None,
    status: str | None = None,
    calendar_id: str | None = None,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """List meal events for the current user."""
    return await ListMealEvents.call(
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
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Create a new meal event."""
    return await CreateMealEvent.call(
        params=params,
        user=user,
        database=database,
    )


@meal_event_router.get("/meal-events/{event_id}")
async def get_meal_event(
    event_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get meal event details."""
    return await GetMealEvent.call(
        event_id=event_id,
        user=user,
        database=database,
    )


@meal_event_router.put("/meal-events/{event_id}")
async def update_meal_event(
    event_id: str,
    params: UpdateMealEvent.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Update a meal event."""
    return await UpdateMealEvent.call(
        event_id=event_id,
        params=params,
        user=user,
        database=database,
    )


@meal_event_router.delete("/meal-events/{event_id}")
async def delete_meal_event(
    event_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Delete a meal event."""
    return await DeleteMealEvent.call(
        event_id=event_id,
        user=user,
        database=database,
    )


@meal_event_router.post("/meal-events/{event_id}/skip")
async def skip_meal_event(
    event_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Skip a meal event (dismiss notifications)."""
    return await SkipMealEvent.call(
        event_id=event_id,
        user=user,
        database=database,
    )


@meal_event_router.post("/meal-events/{event_id}/invite")
async def invite_participant(
    event_id: str,
    params: InviteParticipant.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Invite a participant to a meal event."""
    return await InviteParticipant.call(
        event_id=event_id,
        params=params,
        user=user,
        database=database,
    )


@meal_event_router.post("/meal-events/{event_id}/respond")
async def respond_to_invite(
    event_id: str,
    params: RespondToInvite.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Respond to a meal event invitation."""
    # Run the endpoint to get the raw success dict so the back-fan
    # branch can decide independently of the response envelope.
    endpoint = RespondToInvite(
        event_id=event_id,
        params=params,
        user=user,
        database=database,
    )
    result = await endpoint.run()

    # partner-4: back-fan the RSVP status to the event owner via the
    # sync notifier on the threadpool.
    if result.get("success"):
        try:
            await notify_via_threadpool(
                _notify_rsvp_on_threadpool,
                meal_event_id=str(event_id),
                responder_id=str(user.id),
                status=params.status,
            )
        except Exception as exc:  # noqa: BLE001 — never fail the RSVP  # pragma: no cover — best-effort notify
            logger.error(
                "meal_event_rsvp: back-fan notify failed event_id=%s err=%s: %s",
                event_id, type(exc).__name__, exc,
            )

    return RespondToInvite.handle_result(result)


@meal_event_router.post("/meal-events/{event_id}/add-to-shopping-list")
async def add_meal_event_to_shopping_list(
    event_id: str,
    params: AddMealEventToShoppingList.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Append a single calendar event's ingredients to a shopping list (mcal-5)."""
    return await AddMealEventToShoppingList.call(
        event_id=event_id,
        params=params,
        user=user,
        database=database,
    )
