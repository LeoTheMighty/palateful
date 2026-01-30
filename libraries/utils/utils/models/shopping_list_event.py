"""ShoppingListEvent model - activity log for real-time sync and history."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.shopping_list import ShoppingList
    from utils.models.user import User


class ShoppingListEvent(Base):
    """Activity log for real-time sync and history.

    Event types:
    - item_added: An item was added to the list
    - item_checked: An item was checked off
    - item_unchecked: An item was unchecked
    - item_removed: An item was deleted
    - item_updated: An item was modified
    - member_joined: A new member joined the list
    - member_left: A member left or was removed
    - list_updated: List settings were modified
    """

    __tablename__ = "shopping_list_events"

    # Event type
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # Event data (flexible JSONB for different event types)
    # Examples:
    # item_added: {"item_id": "...", "name": "Milk", "quantity": 1, "unit": "gallon"}
    # item_checked: {"item_id": "...", "name": "Eggs"}
    # member_joined: {"user_id": "...", "name": "Partner Name"}
    event_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Who triggered this event
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Which list
    shopping_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shopping_lists.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Sequence number for ordering (auto-increment per list)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    user: Mapped["User | None"] = relationship()
    shopping_list: Mapped["ShoppingList"] = relationship()

    __table_args__ = (
        Index(
            "ix_shopping_list_events_list_sequence",
            "shopping_list_id",
            "sequence",
        ),
    )
