"""Add default_shopping_list_id and previous_shopping_list_id to users

Revision ID: a1b2c3d4e5f6
Revises: 224dc8e7975c
Create Date: 2026-03-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '224dc8e7975c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add default_shopping_list_id column to users table
    op.add_column(
        "users",
        sa.Column(
            "default_shopping_list_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_users_default_shopping_list_id",
        "users",
        "shopping_lists",
        ["default_shopping_list_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Create index for faster lookups
    op.create_index(
        "ix_users_default_shopping_list_id",
        "users",
        ["default_shopping_list_id"],
    )

    # Add previous_shopping_list_id column to users table
    op.add_column(
        "users",
        sa.Column(
            "previous_shopping_list_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_users_previous_shopping_list_id",
        "users",
        "shopping_lists",
        ["previous_shopping_list_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Create index for faster lookups
    op.create_index(
        "ix_users_previous_shopping_list_id",
        "users",
        ["previous_shopping_list_id"],
    )


def downgrade() -> None:
    # Drop previous_shopping_list_id
    op.drop_index("ix_users_previous_shopping_list_id", table_name="users")
    op.drop_constraint("fk_users_previous_shopping_list_id", "users", type_="foreignkey")
    op.drop_column("users", "previous_shopping_list_id")

    # Drop default_shopping_list_id
    op.drop_index("ix_users_default_shopping_list_id", table_name="users")
    op.drop_constraint("fk_users_default_shopping_list_id", "users", type_="foreignkey")
    op.drop_column("users", "default_shopping_list_id")
