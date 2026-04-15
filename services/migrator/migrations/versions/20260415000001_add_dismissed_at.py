"""Add dismissed_at column to import_items and import_jobs

Revision ID: d1s2m3s4d6e7
Revises: c1s2t3a4g5e6
Create Date: 2026-04-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1s2m3s4d6e7"
down_revision: str | None = "c1s2t3a4g5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_items",
        sa.Column(
            "dismissed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "import_jobs",
        sa.Column(
            "dismissed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("import_jobs", "dismissed_at")
    op.drop_column("import_items", "dismissed_at")
