"""Add error_logs.import_item_id + stage + partial index for telemetry.

Revision ID: irrd2tlm0001
Revises: irrd1fields0
Create Date: 2026-04-18

Story irrd-2. The epic text assumed `error_logs.import_item_id` was
already there; it wasn't. Two nullable columns land here so stage
transitions can be tagged per-item + per-stage, plus the partial
index the telemetry endpoint's P95 budget depends on.

Both columns are nullable — the existing error rows (API errors,
`UnitAliasMiss` audits, etc.) don't have an item id or a stage, and we
don't backfill historical rows. Going forward, `log_stage_transition`
is the only sanctioned writer that populates these.

The index is partial (`WHERE import_item_id IS NOT NULL`) and created
`CONCURRENTLY` inside an `autocommit_block()` so the prod deploy
doesn't take a long lock on the growing error_logs table. Mirrors the
pattern in `20260418030000_add_archive_partial_indexes.py`.

Down-migration drops index then columns cleanly.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "irrd2tlm0001"
down_revision: str | None = "irrd1fields0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Columns first — add_column runs inside a transaction, which is
    # fine because ALTER TABLE ... ADD COLUMN nullable-with-no-default
    # takes only a fast exclusive lock in PG.
    op.add_column(
        "error_logs",
        sa.Column("import_item_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "error_logs",
        sa.Column("stage", sa.String(32), nullable=True),
    )

    # Index second — must be CONCURRENTLY (partial hot-path index over a
    # large table). autocommit_block() breaks out of the migration
    # transaction so PG will accept `CREATE INDEX CONCURRENTLY`.
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_error_logs_import_item_created
            ON error_logs (import_item_id, created_at DESC)
            WHERE import_item_id IS NOT NULL
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_error_logs_import_item_created"
        )
    op.drop_column("error_logs", "stage")
    op.drop_column("error_logs", "import_item_id")
