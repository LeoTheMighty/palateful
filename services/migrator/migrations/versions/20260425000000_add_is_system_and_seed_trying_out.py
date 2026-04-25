"""Add is_system to recipe_books + seed Trying Out per existing user.

Revision ID: rdb1isys001
Revises: unreadnotifidx1
Create Date: 2026-04-25

Story recipe-defaults-1 of epic-recipe-default-books.

Two-part migration:

1. **Schema** — add ``is_system`` boolean to ``recipe_books`` with
   ``nullable=False, server_default=false``. Existing rows back-fill
   to ``false`` (user-created books). Future user-created books continue
   to default to ``false``; only the migration here and the new-user
   provisioning hook (story recipe-defaults-2) set it to ``true``.

2. **Data back-fill** — for every existing user that does not already
   own a system book (``recipe_book_users.role='owner'`` joined to a
   ``recipe_books.is_system=true`` row), insert one ``Trying Out``
   recipe book + the matching owner membership row. Idempotent on
   re-run.

The migration intentionally does NOT touch ``users.default_recipe_book_id``.
Existing users keep their current default (often the onboarding-flow
"My Recipes" book). Story recipe-defaults-2's provisioning hook owns
new-user default-setting; story recipe-defaults-4 audits NULL-default
edge cases on the share-import path.

The epic text mentions a partial unique index
``ix_recipe_books_one_system_per_user_per_kind`` on ``(user_id, name)
WHERE is_system=true``. That's not expressible: ``recipe_books`` has no
``user_id`` column — book ownership lives in ``recipe_book_users``.
A cross-table partial unique constraint isn't standard Postgres. We
rely on app-level idempotency (SELECT-before-INSERT) instead, mirroring
``_ensure_default_calendar`` in ``services/api/src/dependencies.py``.

Downgrade drops the column but does NOT delete seeded books — by then
the column is gone and they're indistinguishable from user-created
books. Removing them would cascade-delete any recipes the user added
post-seed.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "rdb1isys001"
down_revision: str | None = "unreadnotifidx1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TRYING_OUT_NAME = "Trying Out"
BATCH_SIZE = 500


def upgrade() -> None:
    op.add_column(
        "recipe_books",
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    conn = op.get_bind()

    while True:
        users_result = conn.execute(
            sa.text(
                """
                SELECT u.id
                FROM users u
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM recipe_book_users rbu
                    JOIN recipe_books rb ON rb.id = rbu.recipe_book_id
                    WHERE rbu.user_id = u.id
                      AND rbu.role = 'owner'
                      AND rbu.archived_at IS NULL
                      AND rb.is_system = true
                      AND rb.archived_at IS NULL
                )
                LIMIT :limit
                """
            ),
            {"limit": BATCH_SIZE},
        )
        user_ids = [row[0] for row in users_result]
        if not user_ids:
            break

        for user_id in user_ids:
            insert_book_result = conn.execute(
                sa.text(
                    """
                    INSERT INTO recipe_books
                        (id, created_at, updated_at, name, description,
                         is_public, is_shared, is_system)
                    VALUES
                        (gen_random_uuid(), NOW(), NOW(), :name, NULL,
                         false, false, true)
                    RETURNING id
                    """
                ),
                {"name": TRYING_OUT_NAME},
            )
            book_id = insert_book_result.scalar_one()

            # recipe_book_users is a join table with composite PK
            # (user_id, recipe_book_id) — no `id` column.
            conn.execute(
                sa.text(
                    """
                    INSERT INTO recipe_book_users
                        (created_at, updated_at,
                         recipe_book_id, user_id, role)
                    VALUES
                        (NOW(), NOW(),
                         :book_id, :user_id, 'owner')
                    """
                ),
                {"book_id": book_id, "user_id": user_id},
            )


def downgrade() -> None:
    op.drop_column("recipe_books", "is_system")
