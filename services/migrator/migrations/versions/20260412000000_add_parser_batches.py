"""Add parser_batches table and group columns

Revision ID: b1a2t3c4h5e6
Revises: a0p1r2o3f4l5
Create Date: 2026-04-12

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1a2t3c4h5e6"
down_revision: str | None = "a0p1r2o3f4l5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parser_batches",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("recipe_book_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("group_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_parser_batches_user_id",
        ),
        sa.ForeignKeyConstraint(
            ["recipe_book_id"], ["recipe_books.id"], ondelete="SET NULL",
            name="fk_parser_batches_recipe_book_id",
        ),
    )
    op.create_index(
        "ix_parser_batches_user_id", "parser_batches", ["user_id"]
    )
    op.create_index(
        "ix_parser_batches_status", "parser_batches", ["status"]
    )

    op.add_column(
        "parser_jobs",
        sa.Column("parser_batch_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "parser_jobs",
        sa.Column(
            "group_index",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "ix_parser_jobs_parser_batch_id",
        "parser_jobs",
        ["parser_batch_id"],
    )
    op.create_foreign_key(
        "fk_parser_jobs_parser_batch_id",
        "parser_jobs",
        "parser_batches",
        ["parser_batch_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column(
        "import_jobs",
        sa.Column("parser_batch_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_import_jobs_parser_batch_id",
        "import_jobs",
        "parser_batches",
        ["parser_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_import_jobs_parser_batch_id", "import_jobs", type_="foreignkey"
    )
    op.drop_column("import_jobs", "parser_batch_id")

    op.drop_constraint(
        "fk_parser_jobs_parser_batch_id", "parser_jobs", type_="foreignkey"
    )
    op.drop_index("ix_parser_jobs_parser_batch_id", table_name="parser_jobs")
    op.drop_column("parser_jobs", "group_index")
    op.drop_column("parser_jobs", "parser_batch_id")

    op.drop_index("ix_parser_batches_status", table_name="parser_batches")
    op.drop_index("ix_parser_batches_user_id", table_name="parser_batches")
    op.drop_table("parser_batches")
