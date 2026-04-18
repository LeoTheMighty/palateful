"""TaskLatency model — one row per Celery task lifecycle."""

from sqlalchemy import CheckConstraint, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from utils.models.base import Base


class TaskLatency(Base):
    """Append-only latency sample for a single Celery task lifecycle.

    Written by the signal handlers in
    `libraries/utils/utils/services/observability/celery_hooks.py`. One row
    per (task_id, lifecycle outcome): a task that fails-then-succeeds on
    retry produces two rows (`status='retry'`, then `status='success'`).

    Queried by the `/v1/admin/metrics/tasks` aggregation endpoint.
    """

    __tablename__ = "task_latencies"

    # id, created_at, updated_at, archived_at inherited from Base
    task_name: Mapped[str] = mapped_column(String(128), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    queue_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'failure', 'retry')",
            name="ck_task_latencies_status",
        ),
        Index(
            "ix_task_latencies_created_task",
            text("created_at DESC"),
            "task_name",
        ),
        Index("ix_task_latencies_created", text("created_at DESC")),
    )
