"""Notification fan-out Celery tasks."""

from utils.tasks.notification_tasks.notify_admins_new_feedback import (
    NotifyAdminsNewFeedbackTask,
)

__all__ = ["NotifyAdminsNewFeedbackTask"]
