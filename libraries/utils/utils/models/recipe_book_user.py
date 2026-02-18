"""RecipeBookUser model - join table for recipe book membership."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.recipe_book import RecipeBook
    from utils.models.user import User


class RecipeBookUser(JoinsBase):
    """RecipeBookUser model - join table for recipe book membership."""

    __tablename__ = "recipe_book_users"

    # created_at, updated_at, archived_at inherited from JoinsBase
    role: Mapped[str] = mapped_column(String, default="member")  # owner, editor, viewer

    # Foreign keys (composite primary key)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    recipe_book_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("recipe_books.id", ondelete="CASCADE"), primary_key=True
    )

    # Who invited this user (null for owners / original members)
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(foreign_keys=[user_id], back_populates="recipe_book_memberships")
    recipe_book: Mapped["RecipeBook"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("user_id", "recipe_book_id", name="uq_recipe_book_users"),
    )
