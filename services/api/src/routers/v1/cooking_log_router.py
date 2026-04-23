"""Cooking log endpoints router.

aam-21: flipped to `get_async_database` + `get_current_user_async`.

Post-cook fan-out (partner-cooked push + 2h feedback-prompt enqueue)
is wrapped in `run_in_threadpool` with its own sync Database session —
both `notify_recipe_cooked_by_partner` (recipe_book domain, aam-11) and
the Celery broker path stay sync for now. The cook write itself
commits on the async session; the fan-out is best-effort and must
never fail the cook response.
"""

import contextlib
import logging

from api.v1.cooking_log import CreateCookingLog, ListCookingLogs
from api.v1.recipe_book.notifications import notify_recipe_cooked_by_partner
from dependencies import get_async_database, get_current_user_async
from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from utils.models.recipe import Recipe
from utils.models.user import User
from utils.services.async_database import AsyncDatabase
from utils.services.database import Database

logger = logging.getLogger(__name__)

cooking_log_router = APIRouter(tags=["cooking-logs"])


# 2-hour delay (in seconds) for the post-cook feedback prompt.
_COOK_FEEDBACK_DELAY_SECONDS = 7200


@cooking_log_router.get("/cooking-logs")
async def list_cooking_logs(
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """List recently cooked recipes for the current user."""
    return await ListCookingLogs.call(
        limit=limit,
        user=user,
        database=database,
    )


def _run_post_cook_fanout(recipe_id: str, parent_log_id: str, user_id: str):
    """Dispatched to the threadpool. Owns its own sync Database session.

    Runs the partner-cooked notify (sync Database + Firebase) and
    schedules the 2h feedback-prompt Celery task. Every failure is
    logged and swallowed — the user's cook response is already done,
    and the fan-out is best-effort (matches the previous sync
    behavior, where each branch had its own try/except).

    The outer try/except also protects against `Database()` failing to
    initialize (e.g. in tests where DATABASE_URL points at an
    unreachable DSN) — tests exercise the cook path itself via the
    async mock; the sync-DB fan-out just no-ops.
    """
    sync_db = None
    try:
        sync_db = Database()
        recipe = sync_db.find_by(Recipe, id=recipe_id)
        if recipe is None:
            return

        try:
            # Actor lookup inside notify_recipe_cooked_by_partner reads
            # from `database.db`, so we need to pass a User-shaped
            # object or re-fetch. The helper accepts the User model
            # directly.
            from utils.models.user import User as UserModel
            actor = sync_db.find_by(UserModel, id=user_id)
            if actor is not None:
                notify_recipe_cooked_by_partner(
                    recipe=recipe,
                    actor=actor,
                    database=sync_db,
                )
        except Exception as exc:  # noqa: BLE001 — best-effort notify
            logger.error(
                "cooking_log: partner-cooked notify failed cook_log_id=%s err=%s: %s",
                parent_log_id, type(exc).__name__, exc,
            )

        try:
            from utils.tasks.cook_feedback_tasks.cook_feedback_prompt import (
                cook_feedback_prompt_task,
            )
            cook_feedback_prompt_task.apply_async(
                args=[parent_log_id, user_id],
                countdown=_COOK_FEEDBACK_DELAY_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001 — broker outages shouldn't reject the cook
            logger.error(
                "cooking_log: enqueue cook_feedback_prompt failed cook_log_id=%s err=%s: %s",
                parent_log_id, type(exc).__name__, exc,
            )
    except Exception as exc:  # noqa: BLE001 — outer guard: never raise past the threadpool boundary
        logger.error(
            "cooking_log: post-cook fanout aborted cook_log_id=%s err=%s: %s",
            parent_log_id, type(exc).__name__, exc,
        )
    finally:
        if sync_db is not None:
            with contextlib.suppress(Exception):
                sync_db.close()


@cooking_log_router.post("/cooking-logs")
async def create_cooking_log(
    params: CreateCookingLog.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Mark a meal_event as cooked (or log a recipe directly).

    Meal-event path fans out into 1 parent Meal-level log + N child
    recipe-level logs so both "Cooked the Meal on 4/17" (Meal detail)
    and recipe-level "last cooked" queries stay accurate from a single
    user action.
    """
    # `AsyncEndpoint.call()` returns a CustomJSONResponse; we need the
    # raw {success, data, status} dict so the partner-cooked / feedback
    # fan-out can read the created cook-log id.
    endpoint = CreateCookingLog(params=params, user=user, database=database)
    result = await endpoint.run()

    # partner-3: fire partner-cooked push to the recipe owner + enqueue
    # the 2h cook-feedback prompt for the cooker. Only applies to
    # recipe-anchored logs (skip meal-level parent rows).
    data = result.get("data") if isinstance(result, dict) else None
    if result.get("success") and data is not None and getattr(data, "recipe_id", None):
        await run_in_threadpool(
            _run_post_cook_fanout,
            str(data.recipe_id),
            str(data.parent_log_id),
            str(user.id),
        )

    return CreateCookingLog.handle_result(result)
