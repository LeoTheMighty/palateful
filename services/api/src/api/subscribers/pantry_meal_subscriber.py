"""Subscriber for ``MealEventCompleted``.

Decrements matching pantry ingredients when a meal is marked as cooked. Unit
mismatches are skipped silently and logged at WARNING (epic rule:
best-effort, never block the user's "mark as cooked" action).
"""

import logging

from sqlalchemy.orm import selectinload
from utils.events import MealEventCompleted
from utils.models.recipe import Recipe
from utils.services.database import Database
from utils.services.pantry_service import (
    decrement_pantry_from_recipe,
    get_or_create_default_pantry,
)

logger = logging.getLogger(__name__)


def handle_meal_event_completed(event: MealEventCompleted) -> None:
    """Open a fresh DB session and run the decrement best-effort.

    A failure here MUST NOT raise back to the caller: the meal event is
    already committed in the request's session, the user has already seen
    the 200 response. Log at ERROR and move on.
    """
    database = Database()
    try:
        recipe = (
            database.db.query(Recipe)
            .options(selectinload(Recipe.ingredients))
            .filter(Recipe.id == event.recipe_id)
            .first()
        )
        if recipe is None:
            logger.warning(
                "pantry_decrement_skip_no_recipe meal_event_id=%s recipe_id=%s",
                event.meal_event_id,
                event.recipe_id,
            )
            return

        recipe_servings = getattr(recipe, "servings", None)
        if not recipe_servings:
            logger.warning(
                "pantry_decrement_skip_no_recipe_servings meal_event_id=%s recipe_id=%s",
                event.meal_event_id,
                event.recipe_id,
            )
            return

        # meal_event.servings is not a column on MealEvent today — treat
        # every cooked meal as consuming the recipe's full yield (1.0×).
        # If/when meal_event.servings lands, the scale becomes
        # event.servings / recipe.servings.
        servings_scale = 1.0
        if event.servings is not None and recipe_servings:
            servings_scale = float(event.servings) / float(recipe_servings)

        pantry, _membership = get_or_create_default_pantry(event.user_id, database)

        decrement_pantry_from_recipe(
            database,
            pantry_id=pantry.id,
            recipe=recipe,
            servings_scale=servings_scale,
            source_meal_event_id=event.meal_event_id,
        )
    except Exception:
        logger.exception(
            "pantry_decrement_failed meal_event_id=%s recipe_id=%s",
            event.meal_event_id,
            event.recipe_id,
        )
        # Make sure we don't leave a dirty transaction around.
        try:
            database.db.rollback()
        except Exception:  # pragma: no cover — defensive rollback
            logger.exception("pantry_decrement_rollback_failed")
    finally:
        database.close()
