"""Celery tasks for AI-powered suggestions.

These tasks trigger the agent to generate meal suggestions
for users based on various triggers (daily, pantry updates, expiring items).
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from celery import Task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from agent.config import settings

logger = logging.getLogger(__name__)

# Lazy engine initialization for tasks
_engine = None
_session_factory = None


def _get_session_factory():
    """Lazily create the session factory for tasks."""
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
        )
        _session_factory = sessionmaker(
            _engine,
            class_=Session,
            expire_on_commit=False,
        )
    return _session_factory


def get_celery_app():
    """Lazy import celery app to avoid circular imports."""
    from utils.services.celery import celery_app
    return celery_app


class AutoAgentTask(Task):
    """
    Celery task for running the AI suggestion agent.

    This task wraps the agent runner to generate personalized
    meal suggestions for users.
    """

    name = "auto_agent_task"

    def run(
        self,
        user_id: str,
        trigger_type: str = "daily",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run the suggestion agent for a user.

        Args:
            user_id: ID of the user to generate suggestions for
            trigger_type: Type of trigger ("daily", "pantry_update", "expiring")
            context: Additional context for the trigger

        Returns:
            Result dict with created_suggestion_ids and notifications_sent
        """
        logger.info(f"AutoAgentTask starting for user {user_id}, trigger: {trigger_type}")

        try:
            from agent import run_suggestion_agent

            result = run_suggestion_agent(
                user_id=user_id,
                trigger_type=trigger_type,
                context=context,
            )

            logger.info(
                f"AutoAgentTask completed for user {user_id}: "
                f"{len(result.get('created_suggestion_ids', []))} suggestions"
            )

            return {
                "success": True,
                "user_id": user_id,
                "trigger_type": trigger_type,
                "created_suggestion_ids": result.get("created_suggestion_ids", []),
                "notifications_sent": result.get("notifications_sent", 0),
                "current_step": result.get("current_step", "unknown"),
            }

        except Exception as e:
            logger.error(f"AutoAgentTask failed for user {user_id}: {e}")
            return {
                "success": False,
                "user_id": user_id,
                "trigger_type": trigger_type,
                "error": str(e),
            }


class DailySuggestionsTask(Task):
    """
    Celery task for running daily suggestions for all users.

    This is designed to be run on a schedule (e.g., via Celery Beat)
    to generate morning meal suggestions for all users with notifications enabled.
    """

    name = "daily_suggestions_task"

    def run(self) -> dict[str, int]:
        """
        Run daily suggestions for all eligible users.

        Returns:
            Dict with success and error counts
        """
        logger.info("DailySuggestionsTask starting")

        try:
            from agent import run_daily_suggestions_for_all

            result = run_daily_suggestions_for_all()

            logger.info(
                f"DailySuggestionsTask completed: "
                f"{result['success']} success, {result['errors']} errors"
            )

            return result

        except Exception as e:
            logger.error(f"DailySuggestionsTask failed: {e}")
            return {"success": 0, "errors": 1, "error": str(e)}


class ExpiringIngredientsSuggestionsTask(Task):
    """
    Celery task for checking expiring ingredients and triggering suggestions.

    This task finds users with ingredients expiring soon and triggers
    the agent to generate "use it up" suggestions.
    """

    name = "expiring_ingredients_suggestions_task"

    def run(self, days_threshold: int = 3) -> dict[str, Any]:
        """
        Find users with expiring ingredients and generate suggestions.

        Args:
            days_threshold: Number of days until expiration to consider

        Returns:
            Dict with results summary
        """
        logger.info(f"ExpiringIngredientsSuggestionsTask starting (threshold: {days_threshold} days)")

        try:
            result = self._run_expiring_check(days_threshold)
            return result

        except Exception as e:
            logger.error(f"ExpiringIngredientsSuggestionsTask failed: {e}")
            return {"success": 0, "errors": 1, "error": str(e)}

    def _run_expiring_check(self, days_threshold: int) -> dict[str, Any]:
        """Implementation of expiring check."""
        from agent import run_suggestion_agent
        from utils.models import PantryIngredient, PantryUser

        session_factory = _get_session_factory()

        with session_factory() as db:
            # Find pantry ingredients expiring within threshold
            expiry_date = datetime.utcnow() + timedelta(days=days_threshold)

            query = (
                select(PantryUser.user_id)
                .distinct()
                .join(PantryIngredient, PantryIngredient.pantry_id == PantryUser.pantry_id)
                .where(PantryIngredient.expires_at.is_not(None))
                .where(PantryIngredient.expires_at <= expiry_date)
                .where(PantryIngredient.expires_at > datetime.utcnow())
                .where(PantryIngredient.archived_at.is_(None))
            )

            result = db.execute(query)
            user_ids = [str(row[0]) for row in result.fetchall()]

            logger.info(f"Found {len(user_ids)} users with expiring ingredients")

            success_count = 0
            error_count = 0

            for user_id in user_ids:
                try:
                    run_suggestion_agent(
                        user_id=user_id,
                        trigger_type="expiring",
                        context={"days_threshold": days_threshold},
                        db=db,
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error generating expiring suggestions for user {user_id}: {e}")
                    error_count += 1

            return {
                "users_checked": len(user_ids),
                "success": success_count,
                "errors": error_count,
            }


def register_agent_tasks():
    """Register agent tasks with the Celery app."""
    celery_app = get_celery_app()
    celery_app.register_task(AutoAgentTask())
    celery_app.register_task(DailySuggestionsTask())
    celery_app.register_task(ExpiringIngredientsSuggestionsTask())
    logger.info("Agent tasks registered with Celery")


# Convenience functions for calling tasks
def trigger_user_suggestion(user_id: str, trigger_type: str = "daily", context: dict = None):
    """
    Trigger suggestion generation for a user.

    This is a convenience function that delays the AutoAgentTask.
    """
    celery_app = get_celery_app()
    task = celery_app.tasks.get("auto_agent_task")
    if task:
        return task.delay(user_id, trigger_type, context)
    else:
        raise RuntimeError("AutoAgentTask not registered. Call register_agent_tasks() first.")


def trigger_daily_suggestions():
    """
    Trigger daily suggestions for all users.

    This is a convenience function that delays the DailySuggestionsTask.
    """
    celery_app = get_celery_app()
    task = celery_app.tasks.get("daily_suggestions_task")
    if task:
        return task.delay()
    else:
        raise RuntimeError("DailySuggestionsTask not registered. Call register_agent_tasks() first.")


def trigger_expiring_suggestions(days_threshold: int = 3):
    """
    Trigger expiring ingredient suggestions.

    This is a convenience function that delays the ExpiringIngredientsSuggestionsTask.
    """
    celery_app = get_celery_app()
    task = celery_app.tasks.get("expiring_ingredients_suggestions_task")
    if task:
        return task.delay(days_threshold)
    else:
        raise RuntimeError("ExpiringIngredientsSuggestionsTask not registered. Call register_agent_tasks() first.")
