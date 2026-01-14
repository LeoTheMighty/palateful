"""Pantry model."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.pantry_ingredient import PantryIngredient
    from utils.models.pantry_user import PantryUser


class Pantry(Base):
    """Pantry model - represents a user's ingredient storage."""

    __tablename__ = "pantries"

    # id, created_at, updated_at, archived_at inherited from Base
    name: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    members: Mapped[list["PantryUser"]] = relationship(
        back_populates="pantry", cascade="all, delete-orphan"
    )
    pantry_ingredients: Mapped[list["PantryIngredient"]] = relationship(
        back_populates="pantry", cascade="all, delete-orphan"
    )
