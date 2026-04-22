"""Helper for the 2-hour post-cook feedback push.

Split into its own module (rather than folded into `recipe_book.notifications`)
because this notification is fired from a Celery task in the worker
service, not from the API request cycle. Keeping the dispatch helper in
`libraries/utils/utils/services` lets both the worker and the API share
the same code path without either importing across service boundaries.
"""

from __future__ import annotations

from utils.services.notification_copy import cook_feedback_prompt as cook_feedback_prompt_copy
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)


def notify_cook_feedback_prompt(database, user, recipe) -> dict:
    """Dispatch the COOK_FEEDBACK_PROMPT push to the cooker.

    The cooker's per-category / quiet-hours checks apply (inherited from
    `send_to_user`). Image is opportunistically attached from the
    recipe's cover URL when present.
    """
    recipe_name = (getattr(recipe, "name", None) or "your recipe")
    title, body = cook_feedback_prompt_copy(recipe_name=recipe_name)

    notification = PushNotification(
        title=title,
        body=body,
        notification_type=NotificationType.COOK_FEEDBACK_PROMPT,
        data={
            "recipe_id": str(recipe.id),
            "source": "cook_feedback_prompt",
        },
        image_url=getattr(recipe, "image_url", None),
    )

    push_service = get_push_service()
    return push_service.send_to_user(user, notification, database.db)
