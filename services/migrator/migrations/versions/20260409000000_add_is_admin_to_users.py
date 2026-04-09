"""Add is_admin to users

Revision ID: a1d2m3i4n5s6
Revises: v1b3s5d7f9h1
Create Date: 2026-04-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1d2m3i4n5s6"
down_revision: str | None = "v1b3s5d7f9h1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin")
