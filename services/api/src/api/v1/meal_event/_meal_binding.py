"""Shared helpers for binding a Meal to a meal_event / recurrence_rule.

Both `meal_event` and `recurrence_rule` handlers need the same three
operations once mcal-1 landed the `meal_id` column:

  1. reject a request that sets both `recipe_id` and `meal_id` (XOR);
  2. load + authorize a Meal for the caller, rejecting archived meals;
  3. build the `meal_summary` response hydration.

Lives in `meal_event/` (not `meal/`) because recurrence_rule is a
satellite of meal_event, not of meal — and colocating with the primary
caller matches the existing `_access.py` convention in both directories.
The parallel `api/v1/meal/_access.py` that already owns
`require_meal_read` is deliberately NOT extended here — this module
layers an extra archive-guard on top without widening that shared API.
"""

from __future__ import annotations

from api.v1.meal._access import require_meal_read
from pydantic import BaseModel
from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.models.meal import Meal


class MealSummary(BaseModel):
    """Shape returned inside `MealEventResponse.meal_summary` when the
    event/rule is Meal-linked. None when the event/rule is recipe-linked
    or free-text."""

    id: str
    name: str
    component_count: int
    # Top-4 component image URLs, in component order_index ordering.
    # `None` entries preserved so the Flutter collage layout can render
    # placeholders in-place rather than rebalancing.
    image_urls: list[str | None]


def validate_recipe_meal_xor(
    recipe_id: str | None, meal_id: str | None
) -> None:
    """Reject a payload that sets both `recipe_id` and `meal_id`.

    The DB-level check constraint (`ck_meal_events_recipe_xor_meal`)
    enforces the invariant at write time, but returning a clean 422 at
    request time gives the client a usable error code and avoids the
    generic IntegrityError path.
    """
    if recipe_id and meal_id:
        raise APIException(
            status_code=422,
            detail="recipe_id and meal_id are mutually exclusive",
            code=ErrorCode.MEAL_EVENT_RECIPE_XOR_MEAL,
        )


def require_meal_available(db, meal_id: str, user) -> Meal:
    """Load a Meal + authorize the user, rejecting archived meals.

    Wraps `api.v1.meal._access.require_meal_read` with an additional
    archive check — archived meals are a 404 from the calendar's
    perspective because a user can't plan or shop an archived meal.
    """
    meal = require_meal_read(db, meal_id, user)
    if meal.archived_at is not None:
        raise APIException(
            status_code=404,
            detail="Meal not found",
            code=ErrorCode.MEAL_NOT_FOUND,
        )
    return meal


def build_meal_summary(meal: Meal) -> MealSummary:
    """Render a Meal into its calendar-event-facing summary.

    Components are already ordered by `MealRecipe.order_index` (see
    `Meal.components` relationship). Unavailable components (archived
    recipe or book) still contribute to `component_count` because the
    calendar UI shows the planned total, but their image URL is dropped
    from the collage — a stale thumbnail is a worse UX than a blank
    slot.
    """
    image_urls: list[str | None] = []
    for component in meal.components[:4]:
        recipe = component.recipe
        if recipe is None or recipe.archived_at is not None:
            image_urls.append(None)
            continue
        book = recipe.recipe_book
        if book is not None and book.archived_at is not None:
            image_urls.append(None)
            continue
        image_urls.append(recipe.image_url)

    return MealSummary(
        id=str(meal.id),
        name=meal.name,
        component_count=len(meal.components),
        image_urls=image_urls,
    )
