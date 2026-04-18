"""Add partial indexes for archive hot path + see-all on activities and import items.

Revision ID: a1h2r3a4r5c1
Revises: o1b2s3l4a5t1
Create Date: 2026-04-18

The Activity Hub redesign (epic-activity-hub-redesign) ships swipe-to-archive
on user activities and on import items. The `archived_at` column itself
already lives on `JoinsBase` — every model inherits it and every table was
created with the column from the start. Only the state-specific partial
indexes are new:

- Hot-path index: `WHERE archived_at IS NULL` — served by the default feed
  queries (`list_activities`, `list_import_items`, `list_import_jobs`).
- See-all index: `WHERE archived_at IS NOT NULL` — served by the
  Imports-tab "See all" footer which lists archived rows.

`CREATE INDEX CONCURRENTLY` inside an `autocommit_block()` to avoid
table locks on prod RDS. Mirrors the pattern established in
`20260418000000_add_calendar_user_one_owner_active_index.py`.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1h2r3a4r5c1"
down_revision: str | None = "o1b2s3l4a5t1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # user_activities hot path — default feed query orders by
        # created_at DESC scoped to a user with archived_at IS NULL.
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_user_activities_user_created_active
            ON user_activities (user_id, created_at DESC)
            WHERE archived_at IS NULL
            """
        )
        # user_activities see-all — archived rows, newest archive first.
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_user_activities_user_archived
            ON user_activities (user_id, archived_at DESC)
            WHERE archived_at IS NOT NULL
            """
        )
        # import_items hot path — sectioned by import_job_id in
        # list_import_items; created_at DESC within the job.
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_import_items_job_created_active
            ON import_items (import_job_id, created_at DESC)
            WHERE archived_at IS NULL
            """
        )
        # import_items see-all.
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_import_items_job_archived
            ON import_items (import_job_id, archived_at DESC)
            WHERE archived_at IS NOT NULL
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_import_items_job_archived"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_import_items_job_created_active"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_user_activities_user_archived"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_user_activities_user_created_active"
        )
