"""Add meal_event reminder columns + scan index for meal-1.

Revision ID: mealrmndrflds01
Revises: impjobidemp001
Create Date: 2026-04-22

Story meal-1 of epic-notifications-meal-reminders. Adds the two columns
the Celery beat scheduler (meal-3) reads from and writes back to:

    meal_reminder_time      TIME       nullable  -- user's per-meal wall-clock
                                                 -- preference (NULL = slot default)
    last_reminder_sent_at   TIMESTAMPTZ nullable -- idempotency gate: beat sets
                                                 -- this when it fires so the
                                                 -- next tick skips the row

Both nullable + safe to add inside the main transaction (neither column
has a default that would rewrite existing rows).

Composite index `ix_meal_events_reminder_scan` on
`(scheduled_at, last_reminder_sent_at)` supports the scheduler query:

    SELECT * FROM meal_events
     WHERE scheduled_at::date = CURRENT_DATE
       AND (last_reminder_sent_at IS NULL
            OR last_reminder_sent_at < :todays_window_start)
       AND status NOT IN ('completed', 'skipped')

Created CONCURRENTLY in an autocommit_block so prod deploy doesn't lock
the hot meal_events table.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "mealrmndrflds01"
down_revision: str | None = "impjobidemp001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meal_events",
        sa.Column("meal_reminder_time", sa.Time(), nullable=True),
    )
    op.add_column(
        "meal_events",
        sa.Column(
            "last_reminder_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_meal_events_reminder_scan
            ON meal_events (scheduled_at, last_reminder_sent_at)
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_meal_events_reminder_scan"
        )

    op.drop_column("meal_events", "last_reminder_sent_at")
    op.drop_column("meal_events", "meal_reminder_time")
