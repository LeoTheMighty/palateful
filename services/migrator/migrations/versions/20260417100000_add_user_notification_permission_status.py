"""Add notification_permission_status column to users.

Revision ID: n1o2t3i4f5p6
Revises: a1r2e3c4u5r6
Create Date: 2026-04-17

Nullable string column — NULL for pre-notif-4 users (no onboarding
prompt ever shown), "granted" / "provisional" / "declined" otherwise.
Reflects the OS AuthorizationStatus outcome, not which button the user
tapped during onboarding, so the in-app state matches reality.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n1o2t3i4f5p6"
down_revision: str | None = "c1a2l3d4r5s6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("notification_permission_status", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "notification_permission_status")
