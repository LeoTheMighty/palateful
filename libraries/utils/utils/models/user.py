"""User model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.import_job import ImportJob
    from utils.models.ingredient import Ingredient
    from utils.models.notification import Notification
    from utils.models.pantry_user import PantryUser
    from utils.models.recipe_book import RecipeBook
    from utils.models.recipe_book_user import RecipeBookUser
    from utils.models.shopping_list_user import ShoppingListUser
    from utils.models.suggestion import Suggestion
    from utils.models.thread import Thread


class User(Base):
    """User model - corresponds to Auth0 users."""

    __tablename__ = "users"

    # Override id to use String (auth0_id based)
    auth0_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    picture: Mapped[str | None] = mapped_column(String, nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    has_completed_onboarding: Mapped[bool] = mapped_column(Boolean, default=False)

    # Default recipe book for the user (opened on home screen)
    default_recipe_book_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recipe_books.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Notification settings
    notification_preferences: Mapped[dict | None] = mapped_column(
        JSONB,
        default={
            "push_enabled": True,
            "email_digest": "daily",
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
            "timezone": "America/Denver",
        },
        nullable=True,
    )
    push_tokens: Mapped[list | None] = mapped_column(JSONB, default=[], nullable=True)

    # Relationships
    default_recipe_book: Mapped["RecipeBook | None"] = relationship(
        foreign_keys=[default_recipe_book_id],
    )
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
    suggestions: Mapped[list["Suggestion"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    import_jobs: Mapped[list["ImportJob"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    shopping_list_memberships: Mapped[list["ShoppingListUser"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
