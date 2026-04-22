"""Per-user-per-list idempotency state for shopping-deadline reminders."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.shopping_list import ShoppingList
    from utils.models.user import User


class ShoppingListUserReminderState(JoinsBase):
    """Tracks when a given user last got a shopping-deadline push for a list.

    Composite PK `(user_id, shopping_list_id)`. One row per (user, list)
    pair; `last_deadline_reminder_sent_at` is updated when the morning
    beat task fires a push to that user for that list. Shared lists
    span users in different timezones and want independent state, so a
    column on `shopping_list` would be wrong — one user's morning push
    would silence the other's (see party-mode review in the epic).

    Inherits created_at/updated_at/archived_at from JoinsBase; no `id`
    column because the composite PK is the row identity.
    """

    __tablename__ = "shopping_list_user_reminder_state"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    shopping_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shopping_lists.id", ondelete="CASCADE"),
        primary_key=True,
    )

    last_deadline_reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    shopping_list: Mapped["ShoppingList"] = relationship(
        foreign_keys=[shopping_list_id]
    )
