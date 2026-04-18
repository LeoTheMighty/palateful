"""RequestLatency model — one row per FastAPI request, batched by the writer."""

import uuid

from sqlalchemy import UUID, ForeignKey, Index, Integer, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from utils.models.base import Base


class RequestLatency(Base):
    """Append-only latency sample for a single API request.

    Written by the `BatchedLatencyWriter` from
    `services/api/src/middleware/latency_capture.py`. Queried by the
    `/v1/admin/metrics/endpoints` aggregation endpoint.

    `normalized_path` is the FastAPI route template (e.g.
    `/v1/recipes/{recipe_id}`), NOT the raw URL — this keeps cardinality
    bounded. `user_id` is SET NULL on user delete so samples survive
    offboarding without dangling FK violations.
    """

    __tablename__ = "request_latencies"

    # id, created_at, updated_at, archived_at inherited from Base
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    normalized_path: Mapped[str] = mapped_column(String(256), nullable=False)
    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index(
            "ix_request_latencies_created_path",
            text("created_at DESC"),
            "normalized_path",
        ),
        Index("ix_request_latencies_created", text("created_at DESC")),
    )
