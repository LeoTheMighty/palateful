"""Push notification helpers for the recipe import pipeline."""

import logging

from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.user import User
from utils.services.notification_copy import import_needs_review
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)

logger = logging.getLogger(__name__)


def notify_import_needs_review(database, job: ImportJob) -> None:
    """Send a push notification telling the user their import is ready to review.

    Single-recipe variant loads the first awaiting-review `ImportItem`
    and pulls `parsed_recipe.name` + `parsed_recipe.image_url` from it
    so the push can show the recipe name in the title and the cover
    image as an attachment. Bulk variant (count > 1) uses the count
    only — no per-item lookup.

    Note: `parsed_recipe.image_url` is the extractor's URL (the URL
    the page embedded). The post-approval source-photo promotion runs
    after this notification fires, so the hero image isn't promoted
    yet — using the extractor URL is the best signal we have here.

    Called from import-pipeline tasks (extract / match / create) the
    moment a job's status transitions into `awaiting_review`. Safe to
    call from a Celery worker context — failures are logged and
    swallowed so they never take down the task.
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

        # Bulk variant: skip the per-item lookup — we don't need name
        # or image. Save the round-trip.
        recipe_name: str | None = None
        image_url: str | None = None
        if review_count == 1:
            item = (
                database.db.query(ImportItem)
                .filter_by(import_job_id=job.id, status="awaiting_review")
                .order_by(ImportItem.created_at)
                .first()
            )
            if item and item.parsed_recipe:
                parsed = item.parsed_recipe
                if isinstance(parsed, dict):
                    name_val = parsed.get("name")
                    if isinstance(name_val, str) and name_val.strip():
                        recipe_name = name_val.strip()
                    img_val = parsed.get("image_url")
                    if isinstance(img_val, str) and img_val.strip():
                        image_url = img_val.strip()

        title, body = import_needs_review(
            recipe_name=recipe_name,
            count=review_count,
        )

        notification = PushNotification(
            title=title,
            body=body,
            notification_type=NotificationType.IMPORT_NEEDS_REVIEW,
            data={
                "import_job_id": str(job.id),
                "review_count": str(review_count),
            },
            image_url=image_url,
        )

        push_service.send_to_user(user, notification, database.db)
    except Exception:
        logger.exception(
            "Failed to send import-needs-review notification for job %s",
            job.id,
        )
