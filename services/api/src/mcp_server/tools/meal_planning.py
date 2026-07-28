"""MCP tools for the meal calendar.

aam-14: tools flipped to `async def` + `await call_endpoint_async(...)`
when the meal_event domain converted.
"""

from __future__ import annotations

from datetime import date, datetime

from api.v1.meal_event.create_meal_event import CreateMealEvent
from api.v1.meal_event.get_meal_event import GetMealEvent
from api.v1.meal_event.list_meal_events import ListMealEvents
from mcp_server.server import call_endpoint_async, mcp

_VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}


def _parse_iso_datetime(value: str, field: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{field} must be an ISO 8601 datetime (e.g., '2026-05-01T18:30:00')"
        ) from exc


def _parse_iso_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{field} must be an ISO 8601 date (e.g., '2026-05-01')"
        ) from exc


@mcp.tool()
async def list_meal_events(
    start_date: str | None = None,
    end_date: str | None = None,
    meal_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> str:
    """List upcoming meals on the calendar. Filter by `start_date`/`end_date`
    (ISO dates like '2026-05-01') or `meal_type`
    ('breakfast'/'lunch'/'dinner'/'snack'). Great for "what's on the menu
    this week?"
    """
    kwargs: dict = {"limit": limit, "offset": offset}
    if start_date is not None:
        kwargs["start_date"] = _parse_iso_date(start_date, "start_date")
    if end_date is not None:
        kwargs["end_date"] = _parse_iso_date(end_date, "end_date")
    if meal_type is not None:
        if meal_type not in _VALID_MEAL_TYPES:
            raise ValueError(
                f"meal_type must be one of: {', '.join(sorted(_VALID_MEAL_TYPES))}"
            )
        kwargs["meal_type"] = meal_type
    return await call_endpoint_async(ListMealEvents, **kwargs)


@mcp.tool()
async def create_meal_event(
    title: str,
    scheduled_at: str,
    meal_type: str,
    recipe_id: str | None = None,
    meal_id: str | None = None,
    calendar_id: str | None = None,
    description: str | None = None,
) -> str:
    """Schedule a meal on the calendar. `scheduled_at` is an ISO 8601 datetime
    string (e.g., '2026-05-01T18:30:00'). `meal_type` must be
    'breakfast', 'lunch', 'dinner', or 'snack'. Pair a `recipe_id` or
    `meal_id` (not both) when planning from an existing recipe or Meal.
    `calendar_id` targets the calendar to write to.
    """
    if meal_type not in _VALID_MEAL_TYPES:
        raise ValueError(
            f"meal_type must be one of: {', '.join(sorted(_VALID_MEAL_TYPES))}"
        )
    scheduled_dt = _parse_iso_datetime(scheduled_at, "scheduled_at")
    # No XOR check here on purpose: `CreateMealEvent` owns
    # `validate_recipe_meal_xor` (calendar epic mcal-3) plus the
    # `ck_meal_events_recipe_xor_meal` constraint. The tool passes both
    # ids straight through so the 422 surfaces as one MCP error string.
    params = CreateMealEvent.Params(
        title=title,
        scheduled_at=scheduled_dt,
        meal_type=meal_type,
        recipe_id=recipe_id,
        meal_id=meal_id,
        calendar_id=calendar_id,
        description=description,
    )
    return await call_endpoint_async(CreateMealEvent, params=params)


@mcp.tool()
async def get_meal_event(event_id: str) -> str:
    """Get the details of a scheduled meal, including recipe info and
    participants. Use when the user asks "what am I making Thursday?"
    """
    return await call_endpoint_async(GetMealEvent, event_id=event_id)
