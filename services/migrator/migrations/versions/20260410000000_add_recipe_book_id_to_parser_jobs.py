"""Add recipe_book_id and import_job_id to parser_jobs

Revision ID: p1p2e3l4i5n6
Revises: e1r2r3l4o5g6
Create Date: 2026-04-10

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p1p2e3l4i5n6"
down_revision: str | None = "e1r2r3l4o5g6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "parser_jobs",
        sa.Column("recipe_book_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "parser_jobs",
        sa.Column("import_job_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_parser_jobs_recipe_book_id",
        "parser_jobs",
        "recipe_books",
        ["recipe_book_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_parser_jobs_import_job_id",
        "parser_jobs",
        "import_jobs",
        ["import_job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_parser_jobs_import_job_id", "parser_jobs", type_="foreignkey")
    op.drop_constraint("fk_parser_jobs_recipe_book_id", "parser_jobs", type_="foreignkey")
    op.drop_column("parser_jobs", "import_job_id")
    op.drop_column("parser_jobs", "recipe_book_id")
