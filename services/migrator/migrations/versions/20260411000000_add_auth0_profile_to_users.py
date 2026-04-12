"""Add auth0_profile to users

Revision ID: a0p1r2o3f4l5
Revises: p1p2e3l4i5n6
Create Date: 2026-04-11

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "a0p1r2o3f4l5"
down_revision: str | None = "p1p2e3l4i5n6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth0_profile", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "auth0_profile")
