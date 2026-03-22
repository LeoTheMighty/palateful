"""User model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.friend_request import FriendRequest
    from utils.models.friendship import Friendship
    from utils.models.import_job import ImportJob
    from utils.models.ingredient import Ingredient
    from utils.models.invitation import Invitation
    from utils.models.notification import Notification
    from utils.models.pantry_user import PantryUser
    from utils.models.parser_job import ParserJob
    from utils.models.recipe_book import RecipeBook
    from utils.models.recipe_book_user import RecipeBookUser
    from utils.models.shopping_list import ShoppingList
    from utils.models.shopping_list_user import ShoppingListUser
    from utils.models.suggestion import Suggestion
    from utils.models.thread import Thread


class User(Base):
    """User model - corresponds to Auth0 users."""

    __tablename__ = "users"

    # Override id to use String (auth0_id based)
    auth0_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    picture: Mapped[str | None] = mapped_column(String, nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    has_completed_onboarding: Mapped[bool] = mapped_column(Boolean, default=False)

    # Username for social features (@username)
    username: Mapped[str | None] = mapped_column(
        String(20), unique=True, index=True, nullable=True
    )
    username_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Default recipe book for the user (opened on home screen)
    default_recipe_book_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recipe_books.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Default shopping list for quick "Add to Cart" actions
    default_shopping_list_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shopping_lists.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Previous default shopping list (for auto-recovery when current is completed)
    previous_shopping_list_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shopping_lists.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
    default_shopping_list: Mapped["ShoppingList | None"] = relationship(
        foreign_keys=[default_shopping_list_id],
    )
    previous_shopping_list: Mapped["ShoppingList | None"] = relationship(
        foreign_keys=[previous_shopping_list_id],
    )
    pantry_memberships: Mapped[list["PantryUser"]] = relationship(
        "PantryUser",
        foreign_keys="[PantryUser.user_id]",
        back_populates="user", cascade="all, delete-orphan",
    )
    recipe_book_memberships: Mapped[list["RecipeBookUser"]] = relationship(
        "RecipeBookUser",
        foreign_keys="[RecipeBookUser.user_id]",
        back_populates="user", cascade="all, delete-orphan",
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
        "Notification",
        foreign_keys="[Notification.user_id]",
        back_populates="user", cascade="all, delete-orphan",
    )
    import_jobs: Mapped[list["ImportJob"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    parser_jobs: Mapped[list["ParserJob"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    shopping_list_memberships: Mapped[list["ShoppingListUser"]] = relationship(
        "ShoppingListUser",
        foreign_keys="[ShoppingListUser.user_id]",
        back_populates="user", cascade="all, delete-orphan",
    )

    # Invitation relationships
    sent_invitations: Mapped[list["Invitation"]] = relationship(
        "Invitation",
        foreign_keys="[Invitation.from_user_id]",
        back_populates="from_user",
        cascade="all, delete-orphan",
    )
    received_invitations: Mapped[list["Invitation"]] = relationship(
        "Invitation",
        foreign_keys="[Invitation.to_user_id]",
        back_populates="to_user",
    )

    # Friendship relationships
    friendships: Mapped[list["Friendship"]] = relationship(
        "Friendship",
        foreign_keys="[Friendship.user_id]",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sent_friend_requests: Mapped[list["FriendRequest"]] = relationship(
        "FriendRequest",
        foreign_keys="[FriendRequest.from_user_id]",
        back_populates="from_user",
        cascade="all, delete-orphan",
    )
    received_friend_requests: Mapped[list["FriendRequest"]] = relationship(
        "FriendRequest",
        foreign_keys="[FriendRequest.to_user_id]",
        back_populates="to_user",
        cascade="all, delete-orphan",
    )
