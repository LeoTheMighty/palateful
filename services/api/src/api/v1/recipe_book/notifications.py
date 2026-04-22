"""Push notification helpers for recipe book events."""

from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.services.database import Database
from utils.services.notification_copy import (
    _resolve_actor_name,
)
from utils.services.notification_copy import (
    recipe_added as recipe_added_copy,
)
from utils.services.notification_copy import (
    recipe_forked as recipe_forked_copy,
)
from utils.services.notification_copy import (
    recipe_note_added as recipe_note_added_copy,
)
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)


def _find_book_owner(recipe_book_id: str, database: Database) -> User | None:
    """Return the active owner of a recipe book, or None if none found.

    Recipe-owner-centric notifications (fork / note / cook) fan to the
    owner of the book the source recipe lives in. If the book has no
    active owner row we silently skip — there is nobody to notify.
    """
    owner_row = database.db.query(RecipeBookUser).filter(
        RecipeBookUser.recipe_book_id == recipe_book_id,
        RecipeBookUser.role == "owner",
        RecipeBookUser.archived_at.is_(None),
    ).first()
    if owner_row is None:
        return None
    return database.db.query(User).filter(User.id == owner_row.user_id).first()


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
    image_url: str | None = None,
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
        image_url: Optional cover image URL — attached to the push so iOS
            renders the recipe photo in the notification.

    Returns:
        Send result
    """
    actor_name = added_by_user.name or "Someone"
    book_name = recipe_book_name or "a shared recipe book"

    title, body = recipe_added_copy(
        actor_name=actor_name,
        recipe_name=recipe_name,
        book_name=book_name,
    )

    notification = PushNotification(
        title=title,
        body=body,
        notification_type=NotificationType.RECIPE_ADDED,
        data={
            "recipe_book_id": recipe_book_id,
            "recipe_book_name": book_name,
            "recipe_name": recipe_name,
        },
        image_url=image_url,
    )

    return notify_recipe_book_members(
        recipe_book_id=recipe_book_id,
        notification=notification,
        database=database,
        exclude_user_id=str(added_by_user.id),
        category="partner_activity",
    )


def notify_recipe_forked(
    source_recipe: Recipe,
    forked_recipe_id: str,
    target_book: RecipeBook,
    actor: User,
    database: Database,
) -> dict:
    """Fire a `RECIPE_FORKED` push to the source recipe's book owner.

    Recipient policy (epic locked):
      * Recipient = owner of the book the source recipe lives in.
      * Self-forks (actor owns the source book) are silent.
      * No-owner / archived-owner → silent no-op.

    Deep-link payload carries `forked_recipe_id` so the tap lands on the
    new copy in the actor's book, not the original.
    """
    owner = _find_book_owner(str(source_recipe.recipe_book_id), database)
    if owner is None or str(owner.id) == str(actor.id):
        return {"success_count": 0, "failure_count": 0, "skipped": "no_recipient"}

    actor_name = _resolve_actor_name(actor)
    recipe_name = source_recipe.name or "a recipe"
    target_book_name = (target_book.name if target_book else None) or "their book"

    title, body = recipe_forked_copy(
        actor_name=actor_name,
        recipe_name=recipe_name,
        target_book_name=target_book_name,
    )

    notification = PushNotification(
        title=title,
        body=body,
        notification_type=NotificationType.RECIPE_FORKED,
        data={
            "forked_recipe_id": forked_recipe_id,
            "source_recipe_id": str(source_recipe.id),
        },
        image_url=source_recipe.image_url,
    )

    push_service = get_push_service()
    return push_service.send_to_user(owner, notification, database.db)


def notify_recipe_note_added(
    recipe: Recipe,
    note_id: str,
    note_body: str,
    actor: User,
    database: Database,
) -> dict:
    """Fire a `RECIPE_NOTE_ADDED` push to the recipe's book owner.

    Recipient policy (epic locked):
      * Recipient = owner of the book the recipe lives in.
      * Self-notes are silent.
      * Non-shared books silently no-op — there is no "partner" in a
        solo book to be a partner.

    The note body is sliced to the copy library's snippet limit by
    `notification_copy.recipe_note_added`; we pass the full body in.
    """
    book = database.find_by(RecipeBook, id=str(recipe.recipe_book_id))
    if book is None or not book.is_shared:
        return {"success_count": 0, "failure_count": 0, "skipped": "book_not_shared"}

    owner = _find_book_owner(str(recipe.recipe_book_id), database)
    if owner is None or str(owner.id) == str(actor.id):
        return {"success_count": 0, "failure_count": 0, "skipped": "no_recipient"}

    actor_name = _resolve_actor_name(actor)
    recipe_name = recipe.name or "a recipe"

    title, body = recipe_note_added_copy(
        actor_name=actor_name,
        recipe_name=recipe_name,
        note_snippet=note_body or "",
    )

    notification = PushNotification(
        title=title,
        body=body,
        notification_type=NotificationType.RECIPE_NOTE_ADDED,
        data={
            "recipe_id": str(recipe.id),
            "note_id": note_id,
        },
        image_url=recipe.image_url,
    )

    push_service = get_push_service()
    return push_service.send_to_user(owner, notification, database.db)
