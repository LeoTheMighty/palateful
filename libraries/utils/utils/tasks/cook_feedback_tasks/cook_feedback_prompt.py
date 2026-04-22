"""2-hour delayed post-cook feedback prompt task.

Triggered from the cooking-log create path via
`cook_feedback_prompt_task.apply_async(args=[cook_log_id, user_id], countdown=7200)`.
The 2-hour delay lives in Celery's broker; if the worker is down at the
scheduled time the task fires when the worker resumes (at-least-once).

Idempotency: `CookingLog.notes IS NOT NULL` means the user already
captured feedback before the 2h prompt hit — in that case we log INFO
and skip the push. The CookingLog model has no `rating` column today,
so `notes` is the signal.
"""

from __future__ import annotations

import logging

from utils.api.endpoint import success
from utils.models.cooking_log import CookingLog
from utils.models.recipe import Recipe
from utils.models.user import User
from utils.services.celery import celery_app
from utils.services.cook_feedback_notifications import notify_cook_feedback_prompt
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)


class CookFeedbackPromptTask(BaseTask):
    """Fire the 2-hour post-cook feedback prompt to the cooker."""

    name = "cook_feedback_prompt"

    def execute(self, cook_log_id: str, user_id: str):
        db = self.database.db

        cook_log = (
            db.query(CookingLog)
            .filter(CookingLog.id == cook_log_id)
            .first()
        )
        if cook_log is None:
            logger.info(
                "cook_feedback_prompt: log not found cook_log_id=%s — skipping",
                cook_log_id,
            )
            return success({"skipped": "log_not_found"})

        # Idempotency: user already recorded feedback before the 2h delay
        # elapsed. Notes is the only column capturing user feedback today.
        if cook_log.notes:
            logger.info(
                "cook_feedback_prompt: user already rated cook_log_id=%s — skipping",
                cook_log_id,
            )
            return success({"skipped": "already_rated"})

        if cook_log.recipe_id is None:
            # Meal-level parent log — no recipe to anchor the prompt.
            logger.info(
                "cook_feedback_prompt: no recipe on cook log cook_log_id=%s — skipping",
                cook_log_id,
            )
            return success({"skipped": "no_recipe"})

        recipe = (
            db.query(Recipe)
            .filter(Recipe.id == cook_log.recipe_id)
            .first()
        )
        if recipe is None:
            logger.info(
                "cook_feedback_prompt: recipe not found cook_log_id=%s recipe_id=%s",
                cook_log_id, cook_log.recipe_id,
            )
            return success({"skipped": "recipe_missing"})

        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            logger.info(
                "cook_feedback_prompt: cooker not found cook_log_id=%s user_id=%s",
                cook_log_id, user_id,
            )
            return success({"skipped": "user_missing"})

        try:
            result = notify_cook_feedback_prompt(
                database=self.database,
                user=user,
                recipe=recipe,
            )
        except Exception as exc:  # noqa: BLE001 — never raise past the task
            logger.error(
                "cook_feedback_prompt: push send failed cook_log_id=%s err=%s: %s",
                cook_log_id, type(exc).__name__, exc,
            )
            return success({"skipped": "send_failed"})

        return success({
            "sent": True,
            "success_count": result.get("success_count", 0),
            "suppressed_by_category": result.get("suppressed_by_category", False),
            "suppressed_by_quiet_hours": result.get("suppressed_by_quiet_hours", False),
        })


cook_feedback_prompt_task = celery_app.register_task(CookFeedbackPromptTask())
