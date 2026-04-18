"""Add request_latencies + task_latencies tables.

Revision ID: o1b2s3l4a5t1
Revises: u1f2e3e4d5b6
Create Date: 2026-04-18

Two append-only tables that feed the /admin/metrics surface added in
obs-latency-2. See architecture addendum 2026-04-18 for schema rationale.

Chained after the user_feedbacks migration (feedback-1) to keep a single
linear alembic history — epics land in parallel but share a head.

Indexing strategy: each table gets a composite
`(created_at DESC, <grouping key>)` index (for the percentile tables that
rank by path / task) plus a `(created_at DESC)` index (for the
"overall p95 24h" stat on the admin dashboard). No partitioning — 30-day
retention via the nightly prune task keeps size bounded at expected scale.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o1b2s3l4a5t1"
down_revision: str | None = "u1f2e3e4d5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "request_latencies",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("method", sa.String(8), nullable=False),
        sa.Column("normalized_path", sa.String(256), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("request_id", sa.String(64), nullable=False),
    )
    op.create_index(
        "ix_request_latencies_created_path",
        "request_latencies",
        [sa.text("created_at DESC"), "normalized_path"],
    )
    op.create_index(
        "ix_request_latencies_created",
        "request_latencies",
        [sa.text("created_at DESC")],
    )

    op.create_table(
        "task_latencies",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("task_name", sa.String(128), nullable=False),
        sa.Column("task_id", sa.String(64), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("queue_name", sa.String(64), nullable=True),
        sa.CheckConstraint(
            "status IN ('success', 'failure', 'retry')",
            name="ck_task_latencies_status",
        ),
    )
    op.create_index(
        "ix_task_latencies_created_task",
        "task_latencies",
        [sa.text("created_at DESC"), "task_name"],
    )
    op.create_index(
        "ix_task_latencies_created",
        "task_latencies",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_latencies_created", table_name="task_latencies"
    )
    op.drop_index(
        "ix_task_latencies_created_task", table_name="task_latencies"
    )
    op.drop_table("task_latencies")

    op.drop_index(
        "ix_request_latencies_created", table_name="request_latencies"
    )
    op.drop_index(
        "ix_request_latencies_created_path", table_name="request_latencies"
    )
    op.drop_table("request_latencies")
