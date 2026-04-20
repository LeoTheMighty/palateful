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


# ImportItem.status values that count as "actionable" for the bottom-nav
# badge and the Imports-tab in-badge. In-progress + needs-review +
# failed. Green (`status='completed' AND created_recipe_id IS NOT NULL`)
# is explicitly excluded — it's not actionable, just history. Job-level
# statuses (`processing`, `awaiting_parser`) are ImportJob values, not
# ImportItem values, so they never match here.
ACTIONABLE_IMPORT_STATUSES: frozenset[str] = frozenset({
    "pending",
    "extracting",
    "matching",
    "awaiting_review",
    "failed",
})


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
        # sbf-3 partial UNIQUE: one ImportItem per S3 key for the
        # presigned-upload path; NULL rows (legacy base64 / url / text)
        # are not covered by the constraint.
        Index(
            "ix_import_items_s3_key_unique",
            "s3_key",
            unique=True,
            postgresql_where=text("s3_key IS NOT NULL"),
        ),
        # abi-1 partial index for the `imports_actionable` count query
        # on GET /v1/activities/unread-count. Indexes the join-partner
        # column (`import_job_id`) + status, so once `import_jobs.user_id
        # = :me` narrows to the user's jobs, the planner seeks directly
        # into this index. Partial `WHERE archived_at IS NULL AND
        # dismissed_at IS NULL` matches the query's visibility gates and
        # keeps the index small.
        Index(
            "ix_import_items_job_status_actionable",
            "import_job_id",
            "status",
            postgresql_where=text(
                "archived_at IS NULL AND dismissed_at IS NULL"
            ),
        ),
    )

    # Status: pending | extracting | matching | awaiting_review | approved | completed | failed | skipped
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)

    # Source reference
    source_type: Mapped[str] = mapped_column(String(20))  # row | url | pdf_page
    source_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Row/page number
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # S3 key for file-based imports uploaded via the presigned-PUT flow
    # (sbf-2/sbf-3). Nullable because the legacy base64 path never sets
    # it, and the `url` / `text` paths never use S3. A partial UNIQUE
    # index (`WHERE s3_key IS NOT NULL`, see migration
    # 20260418070000) blocks replay — a second /import call with the
    # same key returns 409 `duplicate_import`.
    s3_key: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    # Rule path that routed this item into awaiting_review. One of:
    # "low_confidence" | "unmatched_ingredients" | "missing_title" |
    # "manual" | NULL. Set by match/extract tasks at the moment of the
    # status transition; cleared on retry. CHECK-constrained in the DB.
    awaiting_review_reason: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default=None
    )

    # Error handling
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    # Timestamp of the most recent retry dispatch (set by
    # retry_import_item.py). NULL for items that never retried.
    last_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

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
