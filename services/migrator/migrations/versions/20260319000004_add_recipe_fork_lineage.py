"""Add fork lineage columns to recipes table

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-03-19

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k1l2m3n4o5p6"
down_revision: str | None = "j0k1l2m3n4o5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("recipes", sa.Column("forked_from_recipe_id", sa.UUID(), nullable=True))
    op.add_column("recipes", sa.Column("forked_from_book_id", sa.UUID(), nullable=True))
    op.add_column("recipes", sa.Column("forked_from_recipe_name", sa.String(), nullable=True))
    op.add_column("recipes", sa.Column("forked_from_book_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("recipes", "forked_from_book_name")
    op.drop_column("recipes", "forked_from_recipe_name")
    op.drop_column("recipes", "forked_from_book_id")
    op.drop_column("recipes", "forked_from_recipe_id")
