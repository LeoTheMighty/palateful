"""Add partial index on import_items(import_job_id, status) for abi-1.

Revision ID: abi1iiact01
Revises: mcal1mealid01
Create Date: 2026-04-20

Story abi-1 of epic-activity-badge-integrity. Supports the
`imports_actionable` half of the new structured unread-count payload:

    SELECT COUNT(*) FROM import_items
      JOIN import_jobs ON import_items.import_job_id = import_jobs.id
     WHERE import_jobs.user_id = :me
       AND import_items.archived_at IS NULL
       AND import_items.dismissed_at IS NULL
       AND import_items.status IN :ACTIONABLE_IMPORT_STATUSES;

The status set is the `ACTIONABLE_IMPORT_STATUSES` constant in
`libraries/utils/utils/models/import_item.py`. The migration does NOT
inline the list because any future reshaping of what counts as
"actionable" should change only the Python constant — the partial
index predicate stays visibility-only (`archived_at IS NULL AND
dismissed_at IS NULL`), so new statuses don't require a re-index.

`import_items` has no `user_id` column (user lives on `import_jobs`),
so the query joins in. The planner resolves `import_jobs.user_id = :me`
to a narrow set of `import_job_id` values, then seeks this partial
index to count actionable items per job. The partial predicate mirrors
the query's visibility gates (`archived_at IS NULL AND dismissed_at IS
NULL`), which keeps the index small and the seek cheap.

Created CONCURRENTLY inside an `autocommit_block()` so the prod deploy
doesn't take a long lock. Mirrors the pattern in
`20260418060000_add_error_logs_import_item_telemetry.py`.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "abi1iiact01"
down_revision: str | None = "mcal1mealid01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_import_items_job_status_actionable
            ON import_items (import_job_id, status)
            WHERE archived_at IS NULL AND dismissed_at IS NULL
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ix_import_items_job_status_actionable"
        )
