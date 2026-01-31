"""Meal event notification helpers."""

from utils.models.meal_event import MealEvent
from utils.models.user import User
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)


def notify_meal_event_invite(
    meal_event: MealEvent,
    invited_user: User,
    invited_by: User,
    message: str | None = None,
) -> dict:
    """
    Send notification when a user is invited to a meal event.

    Args:
        meal_event: The meal event
        invited_user: The user being invited
        invited_by: The user who sent the invite
        message: Optional custom message from inviter

    Returns:
        Send result with success/failure counts
    """
    push_service = get_push_service()
    if not push_service.is_available:
        return {"success_count": 0, "failure_count": 0, "skipped": "not_configured"}

    body = f"{invited_by.name or 'Someone'} invited you to {meal_event.title or 'a meal event'}"
    if message:
        body = f"{body}: \"{message}\""

    notification = PushNotification(
        title="You're invited to a meal!",
        body=body,
        notification_type=NotificationType.MEAL_EVENT_INVITE,
        data={
            "meal_event_id": str(meal_event.id),
            "meal_event_title": meal_event.title or "",
            "invited_by_id": str(invited_by.id),
            "invited_by_name": invited_by.name or "",
        },
    )

    return push_service.send_to_user(invited_user, notification)


def notify_meal_event_reminder(
    meal_event: MealEvent,
    user: User,
    minutes_until: int,
) -> dict:
    """
    Send reminder notification before a meal event.

    Args:
        meal_event: The meal event
        user: The user to remind
        minutes_until: Minutes until the event

    Returns:
        Send result with success/failure counts
    """
    push_service = get_push_service()
    if not push_service.is_available:
        return {"success_count": 0, "failure_count": 0, "skipped": "not_configured"}

    if minutes_until >= 60:
        time_str = f"{minutes_until // 60} hour{'s' if minutes_until >= 120 else ''}"
    else:
        time_str = f"{minutes_until} minutes"

    notification = PushNotification(
        title=f"Coming up in {time_str}",
        body=meal_event.title or "Your meal event is starting soon",
        notification_type=NotificationType.MEAL_EVENT_REMINDER,
        data={
            "meal_event_id": str(meal_event.id),
            "meal_event_title": meal_event.title or "",
            "minutes_until": str(minutes_until),
        },
    )

    return push_service.send_to_user(user, notification)


def notify_meal_event_updated(
    meal_event: MealEvent,
    updated_by: User,
    users: list[User],
    db_session,
) -> dict:
    """
    Send notification when a meal event is updated.

    Args:
        meal_event: The meal event
        updated_by: The user who made the update
        users: List of users to notify
        db_session: Database session

    Returns:
        Send result with success/failure counts
    """
    push_service = get_push_service()
    if not push_service.is_available:
        return {"success_count": 0, "failure_count": 0, "skipped": "not_configured"}

    # Filter out the user who made the update
    users_to_notify = [u for u in users if str(u.id) != str(updated_by.id)]
    if not users_to_notify:
        return {"success_count": 0, "failure_count": 0, "skipped": "no_recipients"}

    notification = PushNotification(
        title=f"{meal_event.title or 'Meal event'} updated",
        body=f"{updated_by.name or 'Someone'} made changes to the event",
        notification_type=NotificationType.MEAL_EVENT_UPDATED,
        data={
            "meal_event_id": str(meal_event.id),
            "meal_event_title": meal_event.title or "",
        },
    )

    return push_service.send_to_users(users_to_notify, notification, db_session)
