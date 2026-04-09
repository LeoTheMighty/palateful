"""Create error_logs table

Revision ID: e1r2r3l4o5g6
Revises: a1d2m3i4n5s6
Create Date: 2026-04-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1r2r3l4o5g6"
down_revision: str | None = "a1d2m3i4n5s6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "error_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("error_type", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=False),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Integer(), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("path", sa.String(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("service", sa.String(length=20), server_default="api", nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=True),
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
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_error_logs_request_id", "error_logs", ["request_id"])
    op.create_index(
        "ix_error_logs_service_created_at", "error_logs", ["service", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_error_logs_service_created_at", table_name="error_logs")
    op.drop_index("ix_error_logs_request_id", table_name="error_logs")
    op.drop_table("error_logs")
