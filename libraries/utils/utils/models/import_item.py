"""ImportItem model for individual recipes within an import job."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.import_job import ImportJob
    from utils.models.recipe import Recipe


class ImportItem(Base):
    """Individual recipe within an import job."""

    __tablename__ = "import_items"

    # Status: pending | extracting | matching | awaiting_review | approved | completed | failed | skipped
    status: Mapped[str] = mapped_column(String(20), default="pending")

    # Source reference
    source_type: Mapped[str] = mapped_column(String(20))  # row | url | pdf_page
    source_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Row/page number
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Data stages
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    parsed_recipe: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Extracted recipe
    user_edits: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # User modifications

    # Error handling
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Cost tracking (in cents)
    ai_cost_cents: Mapped[int] = mapped_column(Integer, default=0)

    # Foreign keys
    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("import_jobs.id", ondelete="CASCADE")
    )
    created_recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    import_job: Mapped["ImportJob"] = relationship(back_populates="items")
    created_recipe: Mapped["Recipe | None"] = relationship()
