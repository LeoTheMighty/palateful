"""Add parser_jobs table for tracking OCR batch jobs

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create parser_jobs table
    op.create_table(
        "parser_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("batch_job_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("input_s3_key", sa.String(512), nullable=True),
        sa.Column("output_s3_key", sa.String(512), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_parser_jobs_user_id", "parser_jobs", ["user_id"])
    op.create_index("ix_parser_jobs_status", "parser_jobs", ["status"])
    op.create_index("ix_parser_jobs_batch_job_id", "parser_jobs", ["batch_job_id"])


def downgrade() -> None:
    op.drop_index("ix_parser_jobs_batch_job_id", table_name="parser_jobs")
    op.drop_index("ix_parser_jobs_status", table_name="parser_jobs")
    op.drop_index("ix_parser_jobs_user_id", table_name="parser_jobs")
    op.drop_table("parser_jobs")
