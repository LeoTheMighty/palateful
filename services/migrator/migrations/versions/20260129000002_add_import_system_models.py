"""Add recipe import system models

Revision ID: 9c4d5e6f7a8b
Revises: 8b3c4d5e6f7a
Create Date: 2026-01-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9c4d5e6f7a8b"
down_revision: Union[str, None] = "8b3c4d5e6f7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create import_jobs table
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_filename", sa.String(255), nullable=True),
        sa.Column("source_s3_key", sa.String(512), nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_review_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_ai_cost_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("recipe_book_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["recipe_book_id"], ["recipe_books.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_import_jobs_user_id", "import_jobs", ["user_id"])
    op.create_index("ix_import_jobs_recipe_book_id", "import_jobs", ["recipe_book_id"])
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])

    # Create import_items table
    op.create_table(
        "import_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_reference", sa.String(100), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("parsed_recipe", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("user_edits", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_cost_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("import_job_id", sa.UUID(), nullable=False),
        sa.Column("created_recipe_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_recipe_id"], ["recipes.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_import_items_import_job_id", "import_items", ["import_job_id"])
    op.create_index("ix_import_items_status", "import_items", ["status"])

    # Create ingredient_matches table
    op.create_table(
        "ingredient_matches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_text_normalized", sa.Text(), nullable=False),
        sa.Column("matched_ingredient_id", sa.UUID(), nullable=True),
        sa.Column("match_type", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("user_confirmed", sa.Boolean(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["matched_ingredient_id"], ["ingredients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_ingredient_matches_source_text_normalized", "ingredient_matches", ["source_text_normalized"])
    op.create_index("ix_ingredient_matches_user_confirmed", "ingredient_matches", ["user_confirmed"])


def downgrade() -> None:
    # Drop ingredient_matches table
    op.drop_index("ix_ingredient_matches_user_confirmed", table_name="ingredient_matches")
    op.drop_index("ix_ingredient_matches_source_text_normalized", table_name="ingredient_matches")
    op.drop_table("ingredient_matches")

    # Drop import_items table
    op.drop_index("ix_import_items_status", table_name="import_items")
    op.drop_index("ix_import_items_import_job_id", table_name="import_items")
    op.drop_table("import_items")

    # Drop import_jobs table
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_recipe_book_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_user_id", table_name="import_jobs")
    op.drop_table("import_jobs")
