"""Soft-archive orphan import_* user_activities rows.

Revision ID: abi2bsoftarch1
Revises: abi1iiact01
Create Date: 2026-04-20

Story abi-2b of epic-activity-badge-integrity. abi-2a stopped the
pipeline from writing `import_*` rows to `user_activities`; this
migration makes the historical orphans invisible to every list/count
query (which already gate on `archived_at IS NULL`) without losing
them from the DB. Hard DELETE is tracked as a follow-up epic
(`epic-activity-orphan-cleanup`) after one release of soak.

Safety rails:
1. Row count is captured before the UPDATE. If > 100_000, raise
   RuntimeError so a human reviews prod scale before running a large
   write — Leo's current prod is O(10k) at most, so this is a paranoia
   gate, not a normal path.
2. One `service="audit"` error_logs row is written after the UPDATE
   with the affected-row count + type list, mirroring the audit
   pattern from promote_admin.py / fetch_feedback.py ops scripts.
3. Single transaction (Alembic default) — no CONCURRENTLY needed. The
   `type` column is small-cardinality, and the WHERE clause filters a
   small fraction of the table.
4. No CASCADE — we're touching columns, not dropping constraints.

Idempotency: re-running after soft-archive is a no-op because every
matching row already has `archived_at IS NOT NULL`, so the UPDATE
affects zero rows and the audit log records zero.

Downgrade: body is intentionally empty — un-archiving is not an
automatic reverse. If a rollback is needed, run:

    UPDATE user_activities
       SET archived_at = NULL
     WHERE type IN ('import_started','import_complete',
                    'import_needs_review','import_failed')
       AND archived_at >= '<deploy-timestamp>';

…after deciding which rows to restore. Reversing inside `downgrade()`
could un-archive rows archived by other means (manual ops, user
action) and silently corrupt state.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "abi2bsoftarch1"
down_revision: str | None = "abi1iiact01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ORPHAN_TYPES = (
    "import_started",
    "import_complete",
    "import_needs_review",
    "import_failed",
)
_SAFETY_THRESHOLD = 100_000


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Pre-UPDATE safety gate. If orphan count exceeds the threshold,
    # refuse to proceed — forces a human review on large prod scale.
    row_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM user_activities
             WHERE type = ANY(:types)
               AND archived_at IS NULL
            """
        ),
        {"types": list(_ORPHAN_TYPES)},
    ).scalar_one()

    if row_count > _SAFETY_THRESHOLD:
        raise RuntimeError(
            f"aborting orphan soft-archive: {row_count} rows exceed the "
            f"{_SAFETY_THRESHOLD:_} safety threshold; inspect manually "
            "and run the UPDATE in batches before re-applying this "
            "migration."
        )

    # 2. Soft-archive — sets archived_at = NOW() for orphan rows.
    bind.execute(
        sa.text(
            """
            UPDATE user_activities
               SET archived_at = NOW()
             WHERE type = ANY(:types)
               AND archived_at IS NULL
            """
        ),
        {"types": list(_ORPHAN_TYPES)},
    )

    # 3. Audit log — mirror the `service="audit"` pattern used by
    # promote_admin.py / fetch_feedback.py. error_logs is chosen so the
    # audit row is queryable from a single table without polluting
    # api-error dashboards (which filter on `service="api"`).
    bind.execute(
        sa.text(
            """
            INSERT INTO error_logs (
                id, error_type, error_message, service,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                :error_type,
                :error_message,
                :service,
                NOW(),
                NOW()
            )
            """
        ),
        {
            "error_type": "SoftArchiveOrphanActivities",
            "error_message": (
                f"Soft-archived {row_count} orphan import_* "
                f"user_activity rows (types={list(_ORPHAN_TYPES)}) as "
                "part of story abi-2b."
            ),
            "service": "audit",
        },
    )


def downgrade() -> None:
    """No automatic reverse.

    Un-archiving inside downgrade() would un-archive every row that
    currently has `archived_at IS NOT NULL` on the orphan types —
    including rows archived by other means (ops scripts, user action,
    future code paths). That silently corrupts state.

    If a rollback is needed, run the manual UPDATE documented in the
    module docstring with an explicit deploy-timestamp window.
    """
