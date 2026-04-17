"""Backfill default_shopping_list_id for historically-onboarded users.

Revision ID: b1s2l3p4q5r6
Revises: f1p2t3r4y5e6
Create Date: 2026-04-16

One-shot data migration. For every user matching:

    default_shopping_list_id IS NULL
    AND has_completed_onboarding = TRUE

create a shopping list named "Shopping List" owned by that user, and set
it as the user's default. Runs in chunks of 500 to avoid long locks on
large user tables.

Idempotent on re-run: users who already have a default are skipped.
Users who never completed onboarding are intentionally skipped — the
in-app onboarding flow now provisions a list post-commit (see
services/api/src/api/v1/shopping_list/bootstrap.py), so new users don't
need this sweep.

Does NOT resurrect lists for users who deliberately cleaned up after
onboarding (delete-all-lists case): those users have
has_completed_onboarding=TRUE *and* default_shopping_list_id=NULL, which
this backfill targets. If this is a concern for operators, the
filtering can be tightened pre-deploy to also require the user exists
on or before some cutoff timestamp. For the current dogfood population
(a handful of users), the simple filter is sufficient.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1s2l3p4q5r6"
down_revision: str | None = "f1p2t3r4y5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_LIST_NAME = "Shopping List"
BATCH_SIZE = 500


def upgrade() -> None:
    conn = op.get_bind()

    # Fetch candidate users in chunks.
    while True:
        users_result = conn.execute(
            sa.text(
                """
                SELECT id FROM users
                WHERE default_shopping_list_id IS NULL
                  AND has_completed_onboarding = TRUE
                LIMIT :limit
                """
            ),
            {"limit": BATCH_SIZE},
        )
        user_ids = [row[0] for row in users_result]
        if not user_ids:
            break

        for user_id in user_ids:
            # Create a new shopping list owned by this user.
            insert_result = conn.execute(
                sa.text(
                    """
                    INSERT INTO shopping_lists
                        (id, created_at, updated_at, name, status, owner_id)
                    VALUES
                        (gen_random_uuid(), NOW(), NOW(), :name, 'pending', :owner_id)
                    RETURNING id
                    """
                ),
                {"name": DEFAULT_LIST_NAME, "owner_id": user_id},
            )
            new_list_id = insert_result.scalar_one()

            # Point the user's default at the new list.
            conn.execute(
                sa.text(
                    """
                    UPDATE users
                    SET default_shopping_list_id = :list_id, updated_at = NOW()
                    WHERE id = :user_id
                      AND default_shopping_list_id IS NULL
                    """
                ),
                {"list_id": new_list_id, "user_id": user_id},
            )


def downgrade() -> None:
    # No clean downgrade — we'd be deleting user-created default lists
    # which would cascade into shopping list items. Intentional no-op.
    pass
