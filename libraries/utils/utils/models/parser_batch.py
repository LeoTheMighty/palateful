"""ParserBatch model for grouping multi-image OCR submissions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.parser_job import ParserJob
    from utils.models.recipe_book import RecipeBook
    from utils.models.user import User


class ParserBatch(Base):
    """A group of parser jobs submitted together as a single AWS Batch job.

    Jobs sharing a `group_index` within the same batch represent pages of one
    recipe and are merged into a single ImportItem when OCR completes.
    """

    __tablename__ = "parser_batches"

    # Status: pending | submitted | running | partial | succeeded | failed
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )

    # Number of distinct group_index values in the batch (i.e. recipes)
    group_count: Mapped[int] = mapped_column(Integer, default=1)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    recipe_book_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        ForeignKey("recipe_books.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship()
    recipe_book: Mapped["RecipeBook | None"] = relationship()
    parser_jobs: Mapped[list["ParserJob"]] = relationship(
        back_populates="parser_batch",
        cascade="all, delete-orphan",
    )
