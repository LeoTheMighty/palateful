"""Add shopping_list_user_reminder_state join table.

Revision ID: schdrem001
Revises: mealrmndrflds01
Create Date: 2026-04-22

Backs the sched-1 "morning push for due-today shopping items" feature
(epic-notifications-scheduled-reminders). The party-mode review flagged
that putting `last_deadline_reminder_sent_at` on `shopping_lists` would
collide across shared-list users in different timezones — one user's
morning fire would silence the other's. So idempotency is keyed per
`(user_id, shopping_list_id)` instead.

Composite PK keeps the table at one row per (user, list) pair regardless
of how many mornings fire. Cascades follow the parent rows so cleanup is
automatic.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "schdrem001"
down_revision: str | None = "mealrmndrflds01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shopping_list_user_reminder_state",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "shopping_list_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "last_deadline_reminder_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["shopping_list_id"],
            ["shopping_lists.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "shopping_list_id"),
    )


def downgrade() -> None:
    op.drop_table("shopping_list_user_reminder_state")
