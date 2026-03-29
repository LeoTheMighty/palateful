"""Add primary_vibe and secondary_vibe to recipes

Revision ID: v1b3s5d7f9h1
Revises: n2o3p4q5r6s7
Create Date: 2026-03-29

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'v1b3s5d7f9h1'
down_revision: str | None = 'n2o3p4q5r6s7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column("primary_vibe", sa.String(20), nullable=True),
    )
    op.add_column(
        "recipes",
        sa.Column("secondary_vibe", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recipes", "secondary_vibe")
    op.drop_column("recipes", "primary_vibe")
