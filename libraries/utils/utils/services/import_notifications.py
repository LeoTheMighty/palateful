"""Push notification helpers for the recipe import pipeline."""

import logging

from utils.models.import_job import ImportJob
from utils.models.user import User
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)

logger = logging.getLogger(__name__)


def notify_import_needs_review(database, job: ImportJob) -> None:
    """Send a push notification telling the user their import is ready to review.

    Called from import-pipeline tasks (extract / match / create) the moment a
    job's status transitions into `awaiting_review`. Safe to call from a
    Celery worker context — failures are logged and swallowed so they never
    take down the task.
    """
    try:
        push_service = get_push_service()
        if not push_service.is_available:
            return

        user = database.find_by(User, id=job.user_id)
        if not user:
            return

        review_count = job.pending_review_items or 0
        if review_count <= 0:
            return

        if review_count == 1:
            title = "Your recipe is ready to review"
            body = "Tap to confirm the details we extracted."
        else:
            title = "Your recipes are ready to review"
            body = f"{review_count} recipes need a quick check before saving."

        notification = PushNotification(
            title=title,
            body=body,
            notification_type=NotificationType.IMPORT_NEEDS_REVIEW,
            data={
                "import_job_id": str(job.id),
                "review_count": str(review_count),
            },
        )

        push_service.send_to_user(user, notification, database.db)
    except Exception:
        logger.exception(
            "Failed to send import-needs-review notification for job %s",
            job.id,
        )
