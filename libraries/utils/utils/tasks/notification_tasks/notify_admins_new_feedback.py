"""Celery task that fans out a NEW_FEEDBACK push to every active admin.

Triggered by `POST /v1/users/me/feedback` via `celery_app.send_task` so
the user-facing response stays under the 500ms NFR53 budget. FCM latency
is absorbed here.

Behaviour:
- Loads active admins (`is_admin=true AND archived_at IS NULL`).
  Archived admins are silently skipped — an offboarded admin does not
  receive a ping even if they still have FCM tokens registered.
- Calls `PushNotificationService.send_to_user(... force=True)` per admin.
  `force=True` bypasses quiet hours — admin incident/feedback channel is
  by design urgent.
- One FCM failure does not block the rest; each admin is independent.
- Payload carries `{feedback_id, deep_link: "/admin/feedback"}` in the
  `data` blob so the Flutter push handler can deep-link on tap.
- Idempotency: multiple enqueues with the same `feedback_id` will each
  produce one push per admin. The `PushNotificationService` layer does
  not dedupe; by design this is OK — the user-side endpoint dispatches
  exactly once per submission and retries of the Celery task itself
  are the only source of duplication.
"""

from __future__ import annotations

import logging

from utils.api.endpoint import success
from utils.models.user import User
from utils.models.user_feedback import UserFeedback
from utils.services.celery import celery_app
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

_BODY_PREVIEW_CHARS = 120


class NotifyAdminsNewFeedbackTask(BaseTask):
    """Fan a NEW_FEEDBACK push out to every active admin."""

    name = "notify_admins_new_feedback"

    def execute(self, feedback_id: str):
        db = self.database.db

        feedback = (
            db.query(UserFeedback)
            .filter(UserFeedback.id == feedback_id)
            .first()
        )
        if feedback is None:
            logger.warning(
                "notify_admins_new_feedback: feedback not found feedback_id=%s",
                feedback_id,
            )
            return success({"notified_count": 0, "skipped_count": 0, "failed_count": 0})

        author = (
            db.query(User)
            .filter(User.id == feedback.user_id)
            .first()
        )
        author_display = _display_name(author) if author else "someone"

        admins = (
            db.query(User)
            .filter(User.is_admin.is_(True))
            .filter(User.archived_at.is_(None))
            .all()
        )

        push_service = get_push_service()

        notification_title = "New Palateful feedback"
        body_preview = feedback.body[:_BODY_PREVIEW_CHARS]
        category_label = f" · {feedback.category}" if feedback.category else ""
        notification_body = f"From {author_display}{category_label} — {body_preview}"

        notified = 0
        skipped = 0
        failed = 0

        for admin in admins:
            notification = PushNotification(
                title=notification_title,
                body=notification_body,
                notification_type=NotificationType.NEW_FEEDBACK,
                data={
                    "feedback_id": str(feedback.id),
                    "deep_link": "/admin/feedback",
                },
            )
            try:
                result = push_service.send_to_user(
                    admin,
                    notification,
                    db_session=db,
                    force=True,
                )
            except Exception as exc:  # noqa: BLE001 — never halt the fan-out
                failed += 1
                logger.error(
                    "notify_admins_new_feedback: send failed admin_id=%s err=%s: %s",
                    admin.id, type(exc).__name__, exc,
                )
                continue

            if result.get("success_count", 0) > 0 or result.get("log_only"):
                notified += 1
            else:
                skipped += 1

        return success({
            "notified_count": notified,
            "skipped_count": skipped,
            "failed_count": failed,
            "admin_count": len(admins),
        })


def _display_name(user: User) -> str:
    return user.name or user.username or (user.email or "someone")


notify_admins_new_feedback_task = celery_app.register_task(NotifyAdminsNewFeedbackTask())
