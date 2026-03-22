"""Add last_opened_at to recipe_book_users

Revision ID: m1n2o3p4q5r6
Revises: y2z3a4b5c6d7
Create Date: 2026-03-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'm1n2o3p4q5r6'
down_revision: str | None = 'y2z3a4b5c6d7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recipe_book_users",
        sa.Column(
            "last_opened_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("recipe_book_users", "last_opened_at")
