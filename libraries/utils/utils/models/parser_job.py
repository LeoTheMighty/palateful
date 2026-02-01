"""ParserJob model for tracking OCR batch jobs."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.user import User


class ParserJob(Base):
    """Tracks OCR parsing jobs submitted to AWS Batch."""

    __tablename__ = "parser_jobs"

    # AWS Batch job ID
    batch_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status: pending | submitted | running | succeeded | failed
    status: Mapped[str] = mapped_column(String(20), default="pending")

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

    # Foreign key
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE")
    )

    # Relationship
    user: Mapped["User"] = relationship(back_populates="parser_jobs")
