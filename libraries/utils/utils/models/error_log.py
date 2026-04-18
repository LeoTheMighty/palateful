"""ErrorLog model for tracking application errors."""

import uuid

from sqlalchemy import UUID, Index, Integer, String, Text, text
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
    # irrd-2: stage-transition audit rows set these so the per-item
    # telemetry endpoint can filter cheaply via a partial index. Nullable
    # because the vast majority of error_logs rows (API errors, audit
    # writes without a per-item scope) don't have an import-item context.
    import_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID, nullable=True)
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        Index("ix_error_logs_service_created_at", "service", "created_at"),
        # Hot-path partial index for the per-item telemetry endpoint.
        # WHERE import_item_id IS NOT NULL keeps the index small (most
        # rows don't have one). Created CONCURRENTLY in the migration.
        Index(
            "ix_error_logs_import_item_created",
            "import_item_id",
            text("created_at DESC"),
            postgresql_where=text("import_item_id IS NOT NULL"),
        ),
    )
