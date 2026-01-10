"""Pantry models."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from palateful_utils.db.base import Base

if TYPE_CHECKING:
    from palateful_utils.db.models.ingredient import Ingredient
    from palateful_utils.db.models.user import User


class Pantry(Base):
    """Pantry model - represents a user's ingredient storage."""

    __tablename__ = "pantries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    members: Mapped[list["PantryUser"]] = relationship(
        back_populates="pantry", cascade="all, delete-orphan"
    )
    ingredients: Mapped[list["PantryIngredient"]] = relationship(
        back_populates="pantry", cascade="all, delete-orphan"
    )


class PantryUser(Base):
    """PantryUser model - join table for pantry membership."""

    __tablename__ = "pantry_users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String, default="member")  # owner, member
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Foreign keys
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    pantry_id: Mapped[str] = mapped_column(ForeignKey("pantries.id", ondelete="CASCADE"))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="pantry_memberships")
    pantry: Mapped["Pantry"] = relationship(back_populates="members")

    __table_args__ = (UniqueConstraint("user_id", "pantry_id", name="uq_pantry_users"),)


class PantryIngredient(Base):
    """PantryIngredient model - ingredients in a pantry."""

    __tablename__ = "pantry_ingredients"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    quantity_display: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_display: Mapped[str] = mapped_column(String, nullable=False)
    quantity_normalized: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_normalized: Mapped[str] = mapped_column(String, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Foreign keys
    pantry_id: Mapped[str] = mapped_column(ForeignKey("pantries.id", ondelete="CASCADE"))
    ingredient_id: Mapped[str] = mapped_column(ForeignKey("ingredients.id"))

    # Relationships
    pantry: Mapped["Pantry"] = relationship(back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="pantry_ingredients")

    __table_args__ = (
        UniqueConstraint("pantry_id", "ingredient_id", name="uq_pantry_ingredients"),
    )
