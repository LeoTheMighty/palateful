"""Shopping list event logging service for real-time sync."""

import uuid
from typing import Any, Literal

from sqlalchemy import func
from sqlalchemy.orm import Session
from utils.models.shopping_list import ShoppingListItem
from utils.models.shopping_list_event import ShoppingListEvent
from utils.models.user import User

EventType = Literal[
    "item_added",
    "item_checked",
    "item_unchecked",
    "item_removed",
    "item_updated",
    "member_joined",
    "member_left",
    "list_updated",
]


class ShoppingListEventService:
    """Service for creating and managing shopping list events."""

    def __init__(self, db: Session):
        self.db = db

    def _get_next_sequence(self, shopping_list_id: uuid.UUID) -> int:
        """Get the next sequence number for a shopping list."""
        result = (
            self.db.query(func.max(ShoppingListEvent.sequence))
            .filter(ShoppingListEvent.shopping_list_id == shopping_list_id)
            .scalar()
        )
        return (result or 0) + 1

    def create_event(
        self,
        shopping_list_id: uuid.UUID,
        event_type: EventType,
        user_id: uuid.UUID | None,
        event_data: dict[str, Any],
    ) -> ShoppingListEvent:
        """
        Create a new shopping list event.

        Args:
            shopping_list_id: The shopping list's ID
            event_type: Type of event
            user_id: ID of user who triggered the event
            event_data: Additional event data

        Returns:
            Created event
        """
        sequence = self._get_next_sequence(shopping_list_id)

        event = ShoppingListEvent(
            id=uuid.uuid4(),
            shopping_list_id=shopping_list_id,
            event_type=event_type,
            user_id=user_id,
            event_data=event_data,
            sequence=sequence,
        )
        self.db.add(event)
        self.db.flush()  # Get the ID without committing

        return event

    def log_item_added(
        self,
        shopping_list_id: uuid.UUID,
        item: ShoppingListItem,
        user: User,
    ) -> ShoppingListEvent:
        """Log an item being added to the list."""
        return self.create_event(
            shopping_list_id=shopping_list_id,
            event_type="item_added",
            user_id=user.id,
            event_data={
                "item_id": str(item.id),
                "name": item.name,
                "quantity": float(item.quantity) if item.quantity else None,
                "unit": item.unit,
                "category": item.category,
            },
        )

    def log_item_checked(
        self,
        shopping_list_id: uuid.UUID,
        item: ShoppingListItem,
        user: User,
    ) -> ShoppingListEvent:
        """Log an item being checked off."""
        return self.create_event(
            shopping_list_id=shopping_list_id,
            event_type="item_checked",
            user_id=user.id,
            event_data={
                "item_id": str(item.id),
                "name": item.name,
                "checked_by": {
                    "id": str(user.id),
                    "name": user.name,
                },
            },
        )

    def log_item_unchecked(
        self,
        shopping_list_id: uuid.UUID,
        item: ShoppingListItem,
        user: User,
    ) -> ShoppingListEvent:
        """Log an item being unchecked."""
        return self.create_event(
            shopping_list_id=shopping_list_id,
            event_type="item_unchecked",
            user_id=user.id,
            event_data={
                "item_id": str(item.id),
                "name": item.name,
            },
        )

    def log_item_removed(
        self,
        shopping_list_id: uuid.UUID,
        item: ShoppingListItem,
        user: User,
    ) -> ShoppingListEvent:
        """Log an item being removed from the list."""
        return self.create_event(
            shopping_list_id=shopping_list_id,
            event_type="item_removed",
            user_id=user.id,
            event_data={
                "item_id": str(item.id),
                "name": item.name,
            },
        )

    def log_item_updated(
        self,
        shopping_list_id: uuid.UUID,
        item: ShoppingListItem,
        user: User,
        changes: dict[str, Any],
    ) -> ShoppingListEvent:
        """Log an item being updated."""
        return self.create_event(
            shopping_list_id=shopping_list_id,
            event_type="item_updated",
            user_id=user.id,
            event_data={
                "item_id": str(item.id),
                "name": item.name,
                "changes": changes,
            },
        )

    def log_member_joined(
        self,
        shopping_list_id: uuid.UUID,
        member: User,
        added_by: User | None = None,
    ) -> ShoppingListEvent:
        """Log a new member joining the list."""
        return self.create_event(
            shopping_list_id=shopping_list_id,
            event_type="member_joined",
            user_id=added_by.id if added_by else member.id,
            event_data={
                "user_id": str(member.id),
                "name": member.name,
                "email": member.email,
                "added_by": str(added_by.id) if added_by else None,
            },
        )

    def log_member_left(
        self,
        shopping_list_id: uuid.UUID,
        member: User,
        removed_by: User | None = None,
    ) -> ShoppingListEvent:
        """Log a member leaving or being removed from the list."""
        return self.create_event(
            shopping_list_id=shopping_list_id,
            event_type="member_left",
            user_id=removed_by.id if removed_by else member.id,
            event_data={
                "user_id": str(member.id),
                "name": member.name,
                "removed_by": str(removed_by.id) if removed_by else None,
                "was_removed": removed_by is not None and removed_by.id != member.id,
            },
        )

    def log_list_updated(
        self,
        shopping_list_id: uuid.UUID,
        user: User,
        changes: dict[str, Any],
    ) -> ShoppingListEvent:
        """Log the list settings being updated."""
        return self.create_event(
            shopping_list_id=shopping_list_id,
            event_type="list_updated",
            user_id=user.id,
            event_data={
                "changes": changes,
            },
        )

    def get_events_since(
        self,
        shopping_list_id: uuid.UUID,
        since_sequence: int,
        limit: int = 100,
    ) -> list[ShoppingListEvent]:
        """
        Get events since a specific sequence number.

        This is used for sync/catch-up after reconnection.

        Args:
            shopping_list_id: The shopping list's ID
            since_sequence: Get events after this sequence number
            limit: Maximum number of events to return

        Returns:
            List of events in sequence order
        """
        return (
            self.db.query(ShoppingListEvent)
            .filter(ShoppingListEvent.shopping_list_id == shopping_list_id)
            .filter(ShoppingListEvent.sequence > since_sequence)
            .order_by(ShoppingListEvent.sequence)
            .limit(limit)
            .all()
        )

    def get_current_sequence(self, shopping_list_id: uuid.UUID) -> int:
        """Get the current (latest) sequence number for a list."""
        result = (
            self.db.query(func.max(ShoppingListEvent.sequence))
            .filter(ShoppingListEvent.shopping_list_id == shopping_list_id)
            .scalar()
        )
        return result or 0
