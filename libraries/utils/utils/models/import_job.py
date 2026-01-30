"""ImportJob model for tracking recipe import sessions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.import_item import ImportItem
    from utils.models.recipe_book import RecipeBook
    from utils.models.user import User


class ImportJob(Base):
    """Tracks the overall import session."""

    __tablename__ = "import_jobs"

    # Status: pending | processing | awaiting_review | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending")

    # Source info
    source_type: Mapped[str] = mapped_column(String(20))  # spreadsheet | pdf | url | url_list
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Progress
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    processed_items: Mapped[int] = mapped_column(Integer, default=0)
    succeeded_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)
    pending_review_items: Mapped[int] = mapped_column(Integer, default=0)

    # Cost tracking (in cents)
    total_ai_cost_cents: Mapped[int] = mapped_column(Integer, default=0)

    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE")
    )
    recipe_book_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("recipe_books.id", ondelete="CASCADE")
    )

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="import_jobs")
    recipe_book: Mapped["RecipeBook"] = relationship(back_populates="import_jobs")
    items: Mapped[list["ImportItem"]] = relationship(
        back_populates="import_job", cascade="all, delete-orphan"
    )
