"""Cooking log endpoints router."""

import logging

from api.v1.cooking_log import CreateCookingLog, ListCookingLogs
from api.v1.recipe_book.notifications import notify_recipe_cooked_by_partner
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends, Query
from utils.models.recipe import Recipe
from utils.models.user import User
from utils.services.database import Database

logger = logging.getLogger(__name__)

cooking_log_router = APIRouter(tags=["cooking-logs"])


# 2-hour delay (in seconds) for the post-cook feedback prompt.
_COOK_FEEDBACK_DELAY_SECONDS = 7200


@cooking_log_router.get("/cooking-logs")
async def list_cooking_logs(
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List recently cooked recipes for the current user."""
    return ListCookingLogs.call(
        limit=limit,
        user=user,
        database=database,
    )


@cooking_log_router.post("/cooking-logs")
async def create_cooking_log(
    params: CreateCookingLog.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Mark a meal_event as cooked (or log a recipe directly).

    Meal-event path fans out into 1 parent Meal-level log + N child
    recipe-level logs so both "Cooked the Meal on 4/17" (Meal detail)
    and recipe-level "last cooked" queries stay accurate from a single
    user action.
    """
    result = CreateCookingLog.call(
        params=params, user=user, database=database
    )

    # partner-3: fire partner-cooked push to the recipe owner + enqueue
    # the 2h cook-feedback prompt for the cooker. Only applies to
    # recipe-anchored logs (skip meal-level parent rows).
    data = result.get("data") if isinstance(result, dict) else None
    if result.get("success") and data is not None and getattr(data, "recipe_id", None):
        recipe = database.find_by(Recipe, id=data.recipe_id)
        if recipe is not None:
            try:
                notify_recipe_cooked_by_partner(
                    recipe=recipe,
                    actor=user,
                    database=database,
                )
            except Exception as exc:  # noqa: BLE001 — never fail the cook
                logger.error(
                    "cooking_log: partner-cooked notify failed cook_log_id=%s err=%s: %s",
                    data.parent_log_id, type(exc).__name__, exc,
                )

            try:
                # Local import so importing this module stays cheap in test
                # environments that don't configure Celery.
                from utils.tasks.cook_feedback_tasks.cook_feedback_prompt import (
                    cook_feedback_prompt_task,
                )

                cook_feedback_prompt_task.apply_async(
                    args=[str(data.parent_log_id), str(user.id)],
                    countdown=_COOK_FEEDBACK_DELAY_SECONDS,
                )
            except Exception as exc:  # noqa: BLE001 — broker outages shouldn't reject the cook
                logger.error(
                    "cooking_log: enqueue cook_feedback_prompt failed cook_log_id=%s err=%s: %s",
                    data.parent_log_id, type(exc).__name__, exc,
                )

    return result
