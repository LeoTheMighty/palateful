"""Shopping list notification helpers."""

from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User
from utils.services.database import Database
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)


def notify_shopping_list_members(
    shopping_list: ShoppingList,
    notification: PushNotification,
    database: Database,
    exclude_user_id: str | None = None,
) -> dict:
    """
    Send a push notification to all members of a shopping list.

    Args:
        shopping_list: The shopping list
        notification: The notification to send
        database: Database session
        exclude_user_id: User ID to exclude (usually the actor)

    Returns:
        Send result with success/failure counts
    """
    push_service = get_push_service()
    if not push_service.is_available:
        return {"success_count": 0, "failure_count": 0, "skipped": "not_configured"}

    # Get all active members
    members = database.db.query(ShoppingListUser).filter(
        ShoppingListUser.shopping_list_id == shopping_list.id,
        ShoppingListUser.archived_at.is_(None),
    ).all()

    # Get user objects for members (excluding the actor)
    user_ids = [m.user_id for m in members if str(m.user_id) != exclude_user_id]

    # Include owner if not already in members
    if (
        shopping_list.owner_id
        and str(shopping_list.owner_id) != exclude_user_id
        and shopping_list.owner_id not in user_ids
    ):
        user_ids.append(shopping_list.owner_id)

    if not user_ids:
        return {"success_count": 0, "failure_count": 0, "skipped": "no_recipients"}

    users = database.db.query(User).filter(User.id.in_(user_ids)).all()

    return push_service.send_to_users(users, notification, database.db)


def notify_item_added(
    shopping_list: ShoppingList,
    item: ShoppingListItem,
    added_by: User,
    database: Database,
) -> dict:
    """Send notification when an item is added to a shared list."""
    if not shopping_list.is_shared:
        return {"skipped": "not_shared"}

    notification = PushNotification(
        title=f"Item added to {shopping_list.name or 'Shopping List'}",
        body=f"{added_by.name or 'Someone'} added {item.name}",
        notification_type=NotificationType.SHOPPING_ITEM_ADDED,
        data={
            "shopping_list_id": str(shopping_list.id),
            "item_id": str(item.id),
            "item_name": item.name,
        },
    )

    return notify_shopping_list_members(
        shopping_list,
        notification,
        database,
        exclude_user_id=str(added_by.id),
    )


def notify_item_checked(
    shopping_list: ShoppingList,
    item: ShoppingListItem,
    checked_by: User,
    database: Database,
) -> dict:
    """Send notification when an item is checked off."""
    if not shopping_list.is_shared:
        return {"skipped": "not_shared"}

    notification = PushNotification(
        title="Item checked off",
        body=f"{checked_by.name or 'Someone'} got {item.name}",
        notification_type=NotificationType.SHOPPING_ITEM_CHECKED,
        data={
            "shopping_list_id": str(shopping_list.id),
            "item_id": str(item.id),
            "item_name": item.name,
        },
    )

    return notify_shopping_list_members(
        shopping_list,
        notification,
        database,
        exclude_user_id=str(checked_by.id),
    )


def notify_list_shared(
    shopping_list: ShoppingList,
    invited_user: User,
    invited_by: User,
    database: Database,
) -> dict:
    """Send notification when a user is invited to a shopping list."""
    notification = PushNotification(
        title="You've been added to a shopping list!",
        body=f"{invited_by.name or 'Someone'} added you to {shopping_list.name or 'their shopping list'}",
        notification_type=NotificationType.SHOPPING_LIST_SHARED,
        data={
            "shopping_list_id": str(shopping_list.id),
            "shopping_list_name": shopping_list.name or "",
        },
    )

    push_service = get_push_service()
    return push_service.send_to_user(invited_user, notification, database.db)


def notify_member_joined(
    shopping_list: ShoppingList,
    new_member: User,
    database: Database,
) -> dict:
    """Send notification to existing members when someone joins via share code."""
    notification = PushNotification(
        title="New member joined!",
        body=f"{new_member.name or 'Someone'} joined {shopping_list.name or 'your shopping list'}",
        notification_type=NotificationType.MEMBER_JOINED,
        data={
            "shopping_list_id": str(shopping_list.id),
            "user_id": str(new_member.id),
            "user_name": new_member.name or "",
        },
    )

    return notify_shopping_list_members(
        shopping_list,
        notification,
        database,
        exclude_user_id=str(new_member.id),
    )


def notify_list_complete(
    shopping_list: ShoppingList,
    completed_by: User,
    database: Database,
) -> dict:
    """Send notification when all items in a list are checked."""
    notification = PushNotification(
        title="🎉 Shopping Complete!",
        body=f"All items in {shopping_list.name or 'your list'} have been checked off!",
        notification_type=NotificationType.SHOPPING_LIST_COMPLETE,
        data={
            "shopping_list_id": str(shopping_list.id),
        },
    )

    return notify_shopping_list_members(
        shopping_list,
        notification,
        database,
        exclude_user_id=str(completed_by.id),
    )
