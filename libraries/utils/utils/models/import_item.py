"""ImportItem model for individual recipes within an import job."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.import_job import ImportJob
    from utils.models.recipe import Recipe


class ImportItem(Base):
    """Individual recipe within an import job."""

    __tablename__ = "import_items"

    __table_args__ = (
        # Hot-path partial index for the default feed query
        # (`archived_at IS NULL`) used by the Imports-tab sections.
        Index(
            "ix_import_items_job_created_active",
            "import_job_id",
            text("created_at DESC"),
            postgresql_where=text("archived_at IS NULL"),
        ),
        # See-all partial index for the See-all footer.
        Index(
            "ix_import_items_job_archived",
            "import_job_id",
            text("archived_at DESC"),
            postgresql_where=text("archived_at IS NOT NULL"),
        ),
    )

    # Status: pending | extracting | matching | awaiting_review | approved | completed | failed | skipped
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)

    # Source reference
    source_type: Mapped[str] = mapped_column(String(20))  # row | url | pdf_page
    source_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Row/page number
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Data stages
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    parsed_recipe: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Extracted recipe
    user_edits: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # User modifications

    # Last pipeline stage the item completed successfully.
    # One of: "parsed" | "extracted" | "matched" | NULL.
    # Read by the retry endpoint to resume from the next stage instead of
    # starting over.
    last_successful_stage: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default=None
    )

    # Error handling
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Cost tracking (in cents)
    ai_cost_cents: Mapped[int] = mapped_column(Integer, default=0)

    # Hard-dismiss marker. When set, the item is hidden from list endpoints.
    # We do not delete the row — dismissal is a UI hide, not a DB delete,
    # so audit history and debugging are preserved.
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Foreign keys
    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("import_jobs.id", ondelete="CASCADE"), index=True
    )
    created_recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    import_job: Mapped["ImportJob"] = relationship(back_populates="items")
    created_recipe: Mapped["Recipe | None"] = relationship()
