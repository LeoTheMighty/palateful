"""Add See-all count partial indexes for afh-2.

Revision ID: afh2seeallidx1
Revises: singdrop4
Create Date: 2026-04-20

Story afh-2 of epic-activity-full-history. Keeps the new
``/v1/activities/see-all-count`` and ``/v1/import-items/see-all-count``
endpoints under their 50ms p95 budget on a 10k-row table.

Two indexes:

1. ``ix_user_activities_user_read_old`` on ``user_activities(user_id,
   created_at DESC) WHERE read = true AND archived_at IS NULL``. Serves
   the ``read_and_older`` count. The ``NOW() - INTERVAL '30 days'``
   predicate runs at query time (NOW() isn't immutable) — the planner
   uses this index as a seek on the stable ``read = true AND
   archived_at IS NULL`` prefix, then filters by ``created_at``.
2. ``ix_import_items_job_completed_old`` on ``import_items
   (import_job_id, created_at DESC) WHERE archived_at IS NULL AND
   status = 'completed'``. Serves the ``read_and_old_completed``
   count. The count endpoint joins ``import_jobs`` for the
   ``user_id`` filter (import_items has no user_id column). The
   existing ``ix_import_items_job_archived`` covers the ``archived``
   bucket.

``CREATE INDEX CONCURRENTLY`` inside an ``autocommit_block()`` mirrors
the ahr-1 pattern in
``20260418030000_add_archive_partial_indexes.py`` so the migration
does not lock the tables on prod RDS.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "afh2seeallidx1"
down_revision: str | None = "singdrop4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # read-and-older notifications: the second bucket of the
        # Notifications See-all count. Column WHERE is stable; the
        # 30-day cutoff is applied at query time.
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_user_activities_user_read_old
            ON user_activities (user_id, created_at DESC)
            WHERE read = true AND archived_at IS NULL
            """
        )
        # completed-and-older import items: the second bucket of the
        # Imports See-all count. Scoped by import_job_id because
        # import_items.user_id does not exist — tenant isolation lives
        # on the joined import_jobs row.
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_import_items_job_completed_old
            ON import_items (import_job_id, created_at DESC)
            WHERE archived_at IS NULL AND status = 'completed'
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_import_items_job_completed_old"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_user_activities_user_read_old"
        )
