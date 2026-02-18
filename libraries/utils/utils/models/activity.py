"""Activity model - general-purpose changelog/audit trail for shared resources."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.user import User


class Activity(Base):
    """Audit trail entry for actions on shared resources."""

    __tablename__ = "activities"

    # Who performed the action (null for system actions)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Action: "added" | "updated" | "removed" | "checked" | "unchecked" | "invited" | "joined" | "left"
    action: Mapped[str] = mapped_column(String(30), nullable=False)

    # Resource this activity belongs to (e.g., "shopping_list", "recipe_book")
    resource_type: Mapped[str] = mapped_column(String(30), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Sub-resource affected (e.g., "shopping_list_item", "recipe")
    target_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Flexible payload: field_changed, old_value, new_value, etc.
    details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    user: Mapped["User | None"] = relationship()

    __table_args__ = (
        Index("ix_activities_resource_created", "resource_type", "resource_id", "created_at"),
    )

    def __repr__(self) -> str:
        return self.get_repr(["id", "action", "resource_type"])
