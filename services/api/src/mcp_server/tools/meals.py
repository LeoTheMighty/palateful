"""MCP tools for Meals — reusable named groupings of 2+ recipes.

Each tool wraps one foundation Endpoint via `call_endpoint`. Two tools
add an MCP-specific confirmation gate so the AI pauses before
irreversible-feeling writes:

* `remove_recipe_from_meal`: pre-checks the meal's current component
  count. If removing would leave fewer than 2 components, returns
  `CONFIRMATION_REQUIRED` instead of forwarding to the endpoint — the AI
  surfaces the message and asks the user to confirm, add a replacement,
  or archive instead.

* `archive_meal`: queries `meal_events.meal_id` + `meal_recurrence_rules.meal_id`
  for live references (upcoming events / active recurrence rules). If any
  exist AND `confirmed=False`, returns `CONFIRMATION_REQUIRED` with the
  reference list. A follow-up call with `confirmed=True` bypasses the
  gate and archives silently.

All other tools execute without prompting — the user explicitly asked
for the action and the result is reversible (restore, re-add, etc.).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from api.v1.meal.add_recipe_to_meal import AddRecipeToMeal
from api.v1.meal.archive_meal import ArchiveMeal
from api.v1.meal.create_meal import CreateMeal
from api.v1.meal.get_meal import GetMeal
from api.v1.meal.list_meals import ListMeals
from api.v1.meal.remove_recipe_from_meal import RemoveRecipeFromMeal
from api.v1.meal.update_meal import UpdateMeal
from mcp_server.auth import get_current_database
from mcp_server.server import call_endpoint, mcp
from schemas.meal import (
    MealComponentAddRequest,
    MealCreateRequest,
    MealUpdateRequest,
)
from utils.models.meal import Meal
from utils.models.meal_event import MealEvent
from utils.models.meal_recipe import MealRecipe
from utils.models.meal_recurrence_rule import MealRecurrenceRule


@mcp.tool()
def create_meal(
    recipe_book_id: str,
    name: str,
    component_recipe_ids: list[str],
    description: str | None = None,
) -> str:
    """Create a new Meal — a named grouping of 2 or more recipes. Use when the
    user says things like "make me a meal from X and Y" or "bundle these
    recipes." Components must be recipes the user can read. Returns the
    created Meal's id + metadata so the caller can assemble a deep link.
    """
    if len(component_recipe_ids) < 2:
        raise ValueError("component_recipe_ids must have at least 2 entries")
    params = MealCreateRequest(
        name=name,
        description=description,
        component_recipe_ids=component_recipe_ids,
    )
    return call_endpoint(CreateMeal, book_id=recipe_book_id, params=params)


@mcp.tool()
def get_meal(meal_id: str) -> str:
    """Get a Meal by id. Returns name, description, the component recipes
    (with availability markers), and whether the user has favorited it.
    """
    return call_endpoint(GetMeal, meal_id=meal_id)


@mcp.tool()
def list_meals(
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> str:
    """List Meals the user can read. Optional `q` filters by name or
    description (case-insensitive substring match). Use to disambiguate
    names before calling `create_meal` or `add_recipe_to_meal`.
    """
    result = call_endpoint(ListMeals, limit=limit, offset=offset)
    # Client-side `q` filter — foundation's ListMeals doesn't take a
    # search parameter. Kept thin: the AI can always widen `limit` and
    # filter in its prompt. Bypass if the endpoint call errored.
    if q is None or not q.strip():
        return result
    try:
        payload = json.loads(result)
    except (TypeError, ValueError):
        return result
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return result
    needle = q.strip().lower()
    filtered = [
        it
        for it in items
        if isinstance(it, dict)
        and (
            needle in (it.get("name") or "").lower()
            or needle in (it.get("description") or "").lower()
        )
    ]
    payload["items"] = filtered
    payload["total"] = len(filtered)
    return json.dumps(payload, default=str)


@mcp.tool()
def update_meal(
    meal_id: str,
    name: str | None = None,
    description: str | None = None,
) -> str:
    """Update a Meal's name or description. Component changes use
    `add_recipe_to_meal` / `remove_recipe_from_meal`.
    """
    params = MealUpdateRequest(name=name, description=description)
    return call_endpoint(UpdateMeal, meal_id=meal_id, params=params)


@mcp.tool()
def add_recipe_to_meal(
    meal_id: str,
    recipe_id: str,
    order_index: int | None = None,
) -> str:
    """Add a recipe as a component of a Meal. Rejects duplicates (409) and
    unreadable recipes (404).
    """
    params = MealComponentAddRequest(
        recipe_id=recipe_id, order_index=order_index
    )
    return call_endpoint(AddRecipeToMeal, meal_id=meal_id, params=params)


@mcp.tool()
def remove_recipe_from_meal(meal_id: str, recipe_id: str) -> str:
    """Remove a component from a Meal. Rejects if it would leave fewer than
    2 components.

    MCP confirmation gate: if the Meal currently has exactly 2 components,
    this tool returns `CONFIRMATION_REQUIRED` without executing the
    removal — the AI should surface the message and wait for the user to
    confirm, add a replacement first, or archive the Meal instead. At 3+
    components, the removal executes silently.
    """
    database = get_current_database()
    db = database.db
    component_count = (
        db.query(MealRecipe).filter(MealRecipe.meal_id == meal_id).count()
    )
    if component_count == 2:
        return json.dumps(
            {
                "success": False,
                "error": "CONFIRMATION_REQUIRED",
                "reason": (
                    "Removing this recipe would leave the Meal with only 1 "
                    "component. Confirm, add a replacement first, or archive "
                    "the Meal instead."
                ),
            }
        )
    return call_endpoint(
        RemoveRecipeFromMeal, meal_id=meal_id, recipe_id=recipe_id
    )


@mcp.tool()
def archive_meal(meal_id: str, confirmed: bool = False) -> str:
    """Archive (soft-delete) a Meal. The Meal stays restorable from the
    archive view.

    MCP confirmation gate: if the Meal has upcoming `meal_events` OR
    active `meal_recurrence_rules` that reference it AND `confirmed` is
    False, this tool returns `CONFIRMATION_REQUIRED` with the reference
    list. The AI should surface the message so the user can decide; a
    second call with `confirmed=True` bypasses the gate.

    With `confirmed=True` OR zero references, archives silently.
    """
    if not confirmed:
        database = get_current_database()
        db = database.db
        now = datetime.now(UTC)
        upcoming_events: list[dict[str, Any]] = [
            {
                "id": str(ev.id),
                "title": ev.title,
                "scheduled_at": ev.scheduled_at.isoformat(),
                "meal_type": ev.meal_type,
            }
            for ev in (
                db.query(MealEvent)
                .filter(MealEvent.meal_id == meal_id)
                .filter(MealEvent.archived_at.is_(None))
                .filter(MealEvent.scheduled_at >= now)
                .order_by(MealEvent.scheduled_at)
                .limit(20)
                .all()
            )
        ]
        active_rules: list[dict[str, Any]] = [
            {
                "id": str(rule.id),
                "rrule": getattr(rule, "rrule", None),
                "meal_type": getattr(rule, "meal_type", None),
            }
            for rule in (
                db.query(MealRecurrenceRule)
                .filter(MealRecurrenceRule.meal_id == meal_id)
                .filter(MealRecurrenceRule.archived_at.is_(None))
                .limit(20)
                .all()
            )
        ]
        if upcoming_events or active_rules:
            meal = db.query(Meal).filter(Meal.id == meal_id).first()
            return json.dumps(
                {
                    "success": False,
                    "error": "CONFIRMATION_REQUIRED",
                    "reason": (
                        f"Meal"
                        f"{' \"' + meal.name + '\"' if meal else ''}"
                        f" has {len(upcoming_events)} upcoming event(s)"
                        f" and {len(active_rules)} active recurrence rule(s)."
                        " Call archive_meal again with confirmed=True to"
                        " proceed."
                    ),
                    "events": upcoming_events,
                    "rules": active_rules,
                }
            )
    return call_endpoint(ArchiveMeal, meal_id=meal_id)


__all__ = [
    "add_recipe_to_meal",
    "archive_meal",
    "create_meal",
    "get_meal",
    "list_meals",
    "remove_recipe_from_meal",
    "update_meal",
]
