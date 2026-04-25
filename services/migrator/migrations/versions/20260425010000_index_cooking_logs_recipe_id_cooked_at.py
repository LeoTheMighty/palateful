"""Partial index on cooking_logs(recipe_id, cooked_at DESC) for last-cooked queries.

Revision ID: cklogslastck01
Revises: rdb1isys001
Create Date: 2026-04-25

Story recipe-list-org-1 of epic-recipe-list-organization.

The recipe-list endpoints surface ``last_cooked: datetime | null`` per row by
issuing a per-page batched aggregate over ``cooking_logs``:

    SELECT recipe_id, MAX(cooked_at)
    FROM cooking_logs
    WHERE recipe_id IN (...page) AND archived_at IS NULL
    GROUP BY recipe_id

without an index this scans the heap. Once cooking_logs grows past a few
thousand rows per active user, the home grid + book detail screens both
inherit that scan on every load. The partial index narrows the working set
to live rows and orders by ``cooked_at DESC`` so the MAX is the leading
tuple per recipe — index-only scan, plan stays flat as the table grows.

The same index also serves ``ORDER BY last_cooked`` on the list endpoint
(scalar correlated subquery in the ORDER BY clause), so the sort the
table-view UX exposes runs without a sort node.

``CREATE INDEX CONCURRENTLY`` inside an ``autocommit_block()`` mirrors
``20260424000000_add_unread_notifications_partial_index.py`` so prod RDS
isn't locked while the index builds.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cklogslastck01"
down_revision: str | None = "rdb1isys001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_cooking_logs_recipe_id_cooked_at_active
            ON cooking_logs (recipe_id, cooked_at DESC)
            WHERE archived_at IS NULL
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_cooking_logs_recipe_id_cooked_at_active"
        )
