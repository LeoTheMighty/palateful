"""Push notification helpers for friend events.

Sync helpers invoked from `AsyncEndpoint` via `notify_via_threadpool`
(aam-foundations). The bridge injects a fresh sync `Database` so
`_cleanup_invalid_tokens`'s sync `db_session.commit()` works without
contaminating the caller's async session.
"""

from utils.models.user import User
from utils.services.database import Database
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)


def _display_name(user: User) -> str:
    """Match the friends-domain copy convention: prefer @username, then name, then 'Someone'."""
    if user.username:
        return f"@{user.username}"
    return user.name or "Someone"


def notify_friend_request_sent(
    target_user_id: str,
    friend_request_id: str,
    sender: User,
    database: Database,
) -> dict:
    """Notify the recipient that they have a new friend request.

    Re-fetches the target inside the sync session so `_cleanup_invalid_tokens`
    can mutate `target.push_tokens` and commit on the same session.
    """
    target = database.db.query(User).filter(User.id == target_user_id).first()
    if target is None:  # pragma: no cover — guarded by caller
        return {"success_count": 0, "failure_count": 0, "skipped": "target_missing"}

    notification = PushNotification(
        title="Friend Request",
        body=f"{_display_name(sender)} wants to be friends",
        notification_type=NotificationType.FRIEND_REQUEST,
        data={
            "friend_request_id": friend_request_id,
            "from_user_id": str(sender.id),
        },
    )

    push_service = get_push_service()
    return push_service.send_to_user(target, notification, db_session=database.db)


def notify_friend_request_accepted(
    requester_id: str,
    accepter: User,
    database: Database,
) -> dict:
    """Notify the original requester that their friend request was accepted."""
    requester = database.db.query(User).filter(User.id == requester_id).first()
    if requester is None:  # pragma: no cover — guarded by caller
        return {"success_count": 0, "failure_count": 0, "skipped": "requester_missing"}

    notification = PushNotification(
        title="Friend Request Accepted",
        body=f"{_display_name(accepter)} accepted your friend request",
        notification_type=NotificationType.FRIEND_REQUEST_ACCEPTED,
        data={
            "friend_id": str(accepter.id),
        },
    )

    push_service = get_push_service()
    return push_service.send_to_user(requester, notification, db_session=database.db)
