"""Add partial index for the Notifications unread-count snapshot.

Revision ID: unreadnotifidx1
Revises: cla1aclilat01
Create Date: 2026-04-24

The ``unread_count`` snapshot in ``list_activities.py`` (ffm-4) runs
every time the Notifications tab loads — and again every 30s while it
stays mounted (see ``notifications_tab.dart`` tick listener). The
predicate is ``user_id = :uid AND read = false AND archived_at IS NULL
AND type IN (...) AND created_at >= NOW() - INTERVAL '30 days'``.

None of the existing partial indexes match this predicate:

- ``ix_user_activities_user_created_active`` — covers ``archived_at IS
  NULL`` but still has to filter ``read = false`` in the heap.
- ``ix_user_activities_user_read_old`` — wrong polarity (``read =
  true``), for the See-all count.

On users with thousands of read-but-not-archived rows the COUNT walks
all of them. This index narrows to the unread-and-active subset —
index-only scan, size bounded by per-user unread.

``CREATE INDEX CONCURRENTLY`` inside an ``autocommit_block()`` mirrors
``20260420050000_add_see_all_partial_indexes.py`` so prod RDS isn't
locked.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "unreadnotifidx1"
down_revision: str | None = "cla1aclilat01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_user_activities_user_unread_active
            ON user_activities (user_id, type, created_at DESC)
            WHERE read = false AND archived_at IS NULL
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_user_activities_user_unread_active"
        )
