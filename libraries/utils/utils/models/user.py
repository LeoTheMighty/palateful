"""User model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from palateful_utils.db.base import Base

if TYPE_CHECKING:
    from palateful_utils.db.models.ingredient import Ingredient
    from palateful_utils.db.models.pantry import PantryUser
    from palateful_utils.db.models.recipe import RecipeBookUser
    from palateful_utils.db.models.thread import Thread


class User(Base):
    """User model - corresponds to Auth0 users."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    auth0_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    picture: Mapped[str | None] = mapped_column(String, nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    has_completed_onboarding: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    pantry_memberships: Mapped[list["PantryUser"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    recipe_book_memberships: Mapped[list["RecipeBookUser"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    submitted_ingredients: Mapped[list["Ingredient"]] = relationship(
        back_populates="submitted_by"
    )
    threads: Mapped[list["Thread"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
