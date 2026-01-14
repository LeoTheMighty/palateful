"""Add default_recipe_book_id to users

Revision ID: 7a2d3e4f5b6c
Revises: 525891f38d8b
Create Date: 2026-01-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a2d3e4f5b6c'
down_revision: Union[str, None] = '525891f38d8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add default_recipe_book_id column to users table
    op.add_column(
        "users",
        sa.Column(
            "default_recipe_book_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_users_default_recipe_book_id",
        "users",
        "recipe_books",
        ["default_recipe_book_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Create index for faster lookups
    op.create_index(
        "ix_users_default_recipe_book_id",
        "users",
        ["default_recipe_book_id"],
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_users_default_recipe_book_id", table_name="users")

    # Drop foreign key constraint
    op.drop_constraint("fk_users_default_recipe_book_id", "users", type_="foreignkey")

    # Drop column
    op.drop_column("users", "default_recipe_book_id")
