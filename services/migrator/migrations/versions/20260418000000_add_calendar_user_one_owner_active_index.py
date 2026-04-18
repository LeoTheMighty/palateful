"""Add partial unique index enforcing one active owner per calendar.

Revision ID: c8s1h2a3r4e1
Revises: n1o2t3i4f5p6
Create Date: 2026-04-18

Cal-share-2 introduces ownership transfer (`PATCH /calendars/{id}/members/{user_id}`).
The handler serializes concurrent transfers via row-level `SELECT ... FOR UPDATE`,
but the partial unique index here is the DB-level last-line guarantee that we
never end up with two simultaneous owners on the same calendar.

`CREATE UNIQUE INDEX CONCURRENTLY` so the migration is non-blocking on prod;
`IF NOT EXISTS` keeps the migration idempotent.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8s1h2a3r4e1"
down_revision: str | None = "n1o2t3i4f5p6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # CONCURRENTLY requires running outside a transaction.
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS
                uq_calendar_users_one_owner_active
            ON calendar_users (calendar_id)
            WHERE role = 'owner' AND archived_at IS NULL
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS uq_calendar_users_one_owner_active"
        )
