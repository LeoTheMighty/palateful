"""Add user_feedbacks table for the admin feedback inbox.

Revision ID: u1f2e3e4d5b6
Revises: c8s1h2a3r4e1
Create Date: 2026-04-18

Creates the `user_feedbacks` table for the admin feedback inbox (epic-user-feedback).
Body length is enforced by a CHECK constraint (1..4000) as the DB-level last-line
guarantee matching the Pydantic validation. Status transitions are open to any
value in ('unread','read','archived') — no DB-level ordering since the admin
can flip between Unread ↔ Read freely; Archive is only terminal by convention,
not enforcement.

Indexes target the inbox query pattern: filter by status, order by recency.
`ix_user_feedbacks_status_created` covers the default Unread filter. The
`ix_user_feedbacks_user` index is a safety net for future per-user lookups
(not currently used by the v1 inbox).

`notification_type` is a VARCHAR(50) in the `notifications` table, not a
Postgres ENUM — so no ALTER TYPE is required to add NEW_FEEDBACK. The new
value is only enforced at the Python enum layer.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "u1f2e3e4d5b6"
down_revision: str | None = "c8s1h2a3r4e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_feedbacks",
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
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(16), nullable=True),
        sa.Column("context", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'unread'"),
        ),
        sa.CheckConstraint(
            "length(body) BETWEEN 1 AND 4000",
            name="ck_user_feedbacks_body_length",
        ),
        sa.CheckConstraint(
            "category IS NULL OR category IN ('bug', 'idea', 'praise', 'other')",
            name="ck_user_feedbacks_category",
        ),
        sa.CheckConstraint(
            "status IN ('unread', 'read', 'archived')",
            name="ck_user_feedbacks_status",
        ),
    )
    op.create_index(
        "ix_user_feedbacks_status_created",
        "user_feedbacks",
        ["status", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_user_feedbacks_user",
        "user_feedbacks",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_feedbacks_user", table_name="user_feedbacks"
    )
    op.drop_index(
        "ix_user_feedbacks_status_created", table_name="user_feedbacks"
    )
    op.drop_table("user_feedbacks")
