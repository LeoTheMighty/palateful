"""Add share_token column to recipes table

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-03-20

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l2m3n4o5p6q7"
down_revision: str | None = "k1l2m3n4o5p6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("recipes", sa.Column("share_token", sa.String(20), nullable=True))
    op.create_index(
        "ix_recipes_share_token",
        "recipes",
        ["share_token"],
        unique=True,
        postgresql_where=sa.text("share_token IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_recipes_share_token", table_name="recipes")
    op.drop_column("recipes", "share_token")
