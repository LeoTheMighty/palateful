"""Add lower(trim(name)) index on recipes for duplicate detection.

Revision ID: idupbookname1
Revises: cklogslastck01
Create Date: 2026-04-25

Story `import-dup-1` of `epic-import-duplicate-detection`.

The Approve-Import GET endpoint runs a per-user duplicate-match query:

    SELECT r.id, r.name, r.recipe_book_id, r.archived_at, ...
    FROM recipes r
    WHERE r.recipe_book_id IN (<user's books>)
      AND lower(trim(r.name)) = lower(trim(:title))

Without an index, that scans the full `recipes` table every time the
user opens an Approve-Import screen — unacceptable on a user with
hundreds of recipes (the per-Approve overhead would dominate the screen
first-paint).

This migration adds an expression index on `(recipe_book_id,
lower(trim(name)))`. The planner can then seek directly to the
`recipe_book_id` partition and look up the lower-cased title in one
hop, no table scan.

The epic text references `ix_recipes_user_lower_title` on `(user_id,
lower(trim(title)))`. Two things had to change to fit reality:

1. **`title` → `name`.** The Recipe model column is `name`, not
   `title` — the epic text used the user-facing label.
2. **`user_id` → `recipe_book_id`.** The `recipes` table has no
   `user_id` column; tenant ownership lives on `recipe_books` via the
   `recipe_book_users` join. We scope by the calling user's
   `recipe_book_id IN (...)` list at query time, and the index sits on
   the column we actually filter against.

`CREATE INDEX CONCURRENTLY` inside an `autocommit_block()` mirrors the
existing pattern (see `20260420050000_add_see_all_partial_indexes.py`)
so the migration does not lock the `recipes` table on prod RDS while
backfilling the index.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "idupbookname1"
down_revision: str | None = "cklogslastck01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_recipes_book_lower_name
            ON recipes (recipe_book_id, (lower(trim(name))))
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_recipes_book_lower_name"
        )
