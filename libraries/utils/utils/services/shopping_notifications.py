"""Push notification helpers for the shopping list pipeline."""

import logging

from utils.models.shopping_list import ShoppingList
from utils.models.user import User
from utils.services.notification_copy import shopping_deadline_reminder
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)

logger = logging.getLogger(__name__)


def notify_shopping_deadline_reminder(
    database,
    user: User,
    shopping_list: ShoppingList,
    item_count: int,
) -> None:
    """Fire the morning-of deadline summary push for a shopping list.

    Called from `send_shopping_deadline_reminders` once per (user, list)
    pair that has unchecked items due today in the user's timezone.
    Idempotency (one push per morning per user-list) is the caller's
    responsibility — this helper just sends.

    Per-category prefs (`categories.shopping`) and quiet hours both
    apply via `send_to_user`. Failures are swallowed + logged so a
    single bad push doesn't kill the batch.
    """
    try:
        push_service = get_push_service()
        if not push_service.is_available:
            return

        if item_count <= 0 or shopping_list is None or user is None:
            return

        list_name = shopping_list.name or "your shopping list"
        title, body = shopping_deadline_reminder(
            list_name=list_name,
            item_count=item_count,
        )

        notification = PushNotification(
            title=title,
            body=body,
            notification_type=NotificationType.SHOPPING_DEADLINE_REMINDER,
            data={
                "shopping_list_id": str(shopping_list.id),
                "item_count": str(item_count),
            },
        )

        push_service.send_to_user(user, notification, database.db)
    except Exception:
        logger.exception(
            "Failed to send shopping-deadline reminder "
            "user=%s list=%s",
            getattr(user, "id", None),
            getattr(shopping_list, "id", None),
        )
