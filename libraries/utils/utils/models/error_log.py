"""ErrorLog model for tracking application errors."""

import uuid

from sqlalchemy import UUID, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from utils.models.base import Base


class ErrorLog(Base):
    """ErrorLog model - records application errors for tracking and debugging."""

    __tablename__ = "error_logs"

    # id, created_at, updated_at, archived_at inherited from Base
    error_type: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str] = mapped_column(String, nullable=False)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    path: Mapped[str | None] = mapped_column(String, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID, nullable=True)
    service: Mapped[str] = mapped_column(String(20), default="api")
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    __table_args__ = (
        Index("ix_error_logs_service_created_at", "service", "created_at"),
    )
