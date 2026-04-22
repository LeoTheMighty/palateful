"""Post-cook feedback-prompt Celery tasks."""

from utils.tasks.cook_feedback_tasks.cook_feedback_prompt import (
    CookFeedbackPromptTask,
)

__all__ = ["CookFeedbackPromptTask"]
