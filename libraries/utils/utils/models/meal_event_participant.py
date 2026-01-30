"""MealEventParticipant model - join table for meal event participants."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.meal_event import MealEvent
    from utils.models.user import User


class MealEventParticipant(JoinsBase):
    """A participant in a shared meal event."""

    __tablename__ = "meal_event_participants"

    # Status: invited | accepted | declined | maybe
    status: Mapped[str] = mapped_column(String(20), default="invited")

    # Roles: host | cohost | guest
    role: Mapped[str] = mapped_column(String(20), default="guest")

    # What they're responsible for
    # e.g., ["bring_wine", "prep_salad", "shopping"]
    assigned_tasks: Mapped[list[str] | None] = mapped_column(
        JSONB, default=list, nullable=True
    )

    # Foreign keys (composite primary key)
    meal_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meal_events.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Relationships
    meal_event: Mapped["MealEvent"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "meal_event_id", "user_id", name="uq_meal_event_participants"
        ),
    )
