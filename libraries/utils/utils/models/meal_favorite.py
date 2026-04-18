"""MealFavorite — per-user pinning of a Meal.

Parallels `user_favorites`. Polymorphic unification with `user_favorites`
(one `favorite_type` column) was considered and rejected in the epic —
the extra migration cost isn't worth the flexibility until there's a
third favoritable entity.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.meal import Meal
    from utils.models.user import User


class MealFavorite(JoinsBase):
    """Join table: which Meals a user has favorited."""

    __tablename__ = "meal_favorites"

    # Secondary index on meal_id for "who favorited this Meal" lookups —
    # the composite PK's (user_id, meal_id) index doesn't help that path.
    __table_args__ = (
        Index("ix_meal_favorites_meal_id", "meal_id"),
    )

    # created_at, updated_at, archived_at inherited from JoinsBase

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    meal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meals.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    meal: Mapped["Meal"] = relationship(foreign_keys=[meal_id])
