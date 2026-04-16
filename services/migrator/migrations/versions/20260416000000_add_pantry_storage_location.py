"""Add storage_location column to pantry_ingredients

Revision ID: e1p2t3r4y5a6
Revises: d1s2m3s4d6e7
Create Date: 2026-04-16

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1p2t3r4y5a6"
down_revision: str | None = "d1s2m3s4d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pantry_ingredients",
        sa.Column("storage_location", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pantry_ingredients", "storage_location")
