"""UserFavorite model - join table for user recipe favorites."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.recipe import Recipe
    from utils.models.user import User


class UserFavorite(JoinsBase):
    """UserFavorite model - tracks which recipes a user has favorited."""

    __tablename__ = "user_favorites"

    # created_at, updated_at, archived_at inherited from JoinsBase

    # Foreign keys (composite primary key)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )

    # Relationships
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    recipe: Mapped["Recipe"] = relationship(foreign_keys=[recipe_id])

    __table_args__ = (
        UniqueConstraint("user_id", "recipe_id", name="uq_user_favorites_user_recipe"),
    )
