"""Push notification helpers for recipe book events."""

from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.services.database import Database
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)


def notify_recipe_book_members(
    recipe_book_id: str,
    notification: PushNotification,
    database: Database,
    exclude_user_id: str | None = None,
    category: str | None = None,
) -> dict:
    """
    Send a push notification to all active members of a recipe book.

    Args:
        recipe_book_id: The recipe book ID
        notification: The notification to send
        database: Database session
        exclude_user_id: User ID to exclude (usually the actor)
        category: Optional preference key to filter by (e.g. "partner_activity").
                  Members with this preference set to False are skipped.

    Returns:
        Send result with success/failure counts
    """
    push_service = get_push_service()
    if not push_service.is_available:
        return {"success_count": 0, "failure_count": 0, "skipped": "not_configured"}

    # Get all active members (not archived)
    members = database.db.query(RecipeBookUser).filter(
        RecipeBookUser.recipe_book_id == recipe_book_id,
        RecipeBookUser.archived_at.is_(None),
    ).all()

    # Exclude the actor
    user_ids = [m.user_id for m in members if str(m.user_id) != exclude_user_id]

    if not user_ids:
        return {"success_count": 0, "failure_count": 0, "skipped": "no_recipients"}

    users = database.db.query(User).filter(User.id.in_(user_ids)).all()

    # Filter by category preference if specified
    if category:
        users = [
            u for u in users
            if (u.notification_preferences or {}).get(category, True)
        ]

    if not users:  # pragma: no cover — requires all members to have category disabled
        return {"success_count": 0, "failure_count": 0, "skipped": "no_recipients"}

    return push_service.send_to_users(users, notification, database.db)


def notify_book_shared(
    recipe_book_id: str,
    recipe_book_name: str,
    invited_user: User,
    invited_by: User,
    database: Database,
) -> dict:
    """
    Send a push notification when a recipe book is shared with a user.

    Args:
        recipe_book_id: The recipe book ID
        recipe_book_name: Human-readable book name for notification text
        invited_user: The user being added to the book
        invited_by: The user who added them
        database: Database session

    Returns:
        Send result
    """
    # Check partner_activity preference
    prefs = invited_user.notification_preferences or {}
    if not prefs.get("partner_activity", True):
        return {"success_count": 0, "failure_count": 0, "skipped": "category_disabled"}

    inviter_name = (invited_by.name or "Someone") if invited_by else "Someone"
    book_name = recipe_book_name or "a recipe book"

    notification = PushNotification(
        title="You've been added to a recipe book!",
        body=f"{inviter_name} added you to {book_name}",
        notification_type=NotificationType.RECIPE_BOOK_SHARED,
        data={
            "recipe_book_id": recipe_book_id,
            "recipe_book_name": book_name,
        },
    )

    push_service = get_push_service()
    return push_service.send_to_user(invited_user, notification, database.db)


def notify_recipe_added(
    recipe_book_id: str,
    recipe_book_name: str,
    recipe_name: str,
    added_by_user: User,
    database: Database,
) -> dict:
    """
    Send a push notification when a recipe is added to a shared book.

    Only fires for recipe_added (not updated/removed) — this approximates the
    "notable actions only" batching requirement from the epic spec.

    Args:
        recipe_book_id: The recipe book ID
        recipe_book_name: Human-readable book name for notification text
        recipe_name: Name of the newly added recipe
        added_by_user: The user who added the recipe
        database: Database session

    Returns:
        Send result
    """
    actor_name = added_by_user.name or "Someone"
    book_name = recipe_book_name or "a shared recipe book"

    notification = PushNotification(
        title=f"New recipe in {book_name}",
        body=f"{actor_name} added {recipe_name}",
        notification_type=NotificationType.RECIPE_ADDED,
        data={
            "recipe_book_id": recipe_book_id,
            "recipe_book_name": book_name,
            "recipe_name": recipe_name,
        },
    )

    return notify_recipe_book_members(
        recipe_book_id=recipe_book_id,
        notification=notification,
        database=database,
        exclude_user_id=str(added_by_user.id),
        category="partner_activity",
    )
