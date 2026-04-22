"""ImportJob model for tracking recipe import sessions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.import_item import ImportItem
    from utils.models.recipe_book import RecipeBook
    from utils.models.user import User


class ImportJob(Base):
    """Tracks the overall import session."""

    __tablename__ = "import_jobs"

    __table_args__ = (
        # Replay guard for the Share Extension / reconciler double-fire.
        # Client-supplied opaque token; partial index so the legacy rows
        # (no key) stay out of the index and different users can never
        # collide on the same key.
        Index(
            "ix_import_jobs_user_idempotency_key_unique",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    # Status: pending | processing | awaiting_review | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)

    # Client-supplied replay token. Set by the iOS Share Extension and
    # the Flutter reconciler so a double-fire of `/import` for the same
    # share returns the existing job rather than creating a new one.
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

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
        UUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    recipe_book_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("recipe_books.id", ondelete="CASCADE"), index=True
    )
    parser_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        ForeignKey("parser_batches.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Hard-dismiss marker. Set when every child ImportItem is dismissed or
    # when the job is bulk-dismissed directly. List endpoints filter these
    # out. Row is preserved for audit / debugging.
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="import_jobs")
    recipe_book: Mapped["RecipeBook"] = relationship(back_populates="import_jobs")
    items: Mapped[list["ImportItem"]] = relationship(
        back_populates="import_job", cascade="all, delete-orphan"
    )
