"""Add previous_recipe_book_id to users

Revision ID: y2z3a4b5c6d7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'y2z3a4b5c6d7'
down_revision: str | None = 'x1y2z3a4b5c6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "previous_recipe_book_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_users_previous_recipe_book_id",
        "users",
        "recipe_books",
        ["previous_recipe_book_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_users_previous_recipe_book_id",
        "users",
        ["previous_recipe_book_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_previous_recipe_book_id", table_name="users")
    op.drop_constraint("fk_users_previous_recipe_book_id", "users", type_="foreignkey")
    op.drop_column("users", "previous_recipe_book_id")
