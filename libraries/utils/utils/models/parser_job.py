"""ParserJob model for tracking OCR batch jobs."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.import_job import ImportJob
    from utils.models.recipe_book import RecipeBook
    from utils.models.user import User


class ParserJob(Base):
    """Tracks OCR parsing jobs submitted to AWS Batch."""

    __tablename__ = "parser_jobs"

    # AWS Batch job ID
    batch_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Status: pending | submitted | running | succeeded | failed
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)

    # S3 keys for input/output
    input_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # OCR result
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Error info
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    recipe_book_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("recipe_books.id", ondelete="SET NULL"), nullable=True
    )
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("import_jobs.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="parser_jobs")
    recipe_book: Mapped["RecipeBook | None"] = relationship()
    import_job: Mapped["ImportJob | None"] = relationship()
