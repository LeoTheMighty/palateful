"""Add last_successful_stage column to import_items

Revision ID: c1s2t3a4g5e6
Revises: b1a2t3c4h5e6
Create Date: 2026-04-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1s2t3a4g5e6"
down_revision: str | None = "b1a2t3c4h5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_items",
        sa.Column("last_successful_stage", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("import_items", "last_successful_stage")
