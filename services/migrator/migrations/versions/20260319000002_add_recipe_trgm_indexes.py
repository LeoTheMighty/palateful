"""Add pg_trgm GIN indexes on recipes for fuzzy search

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-03-19

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i9j0k1l2m3n4"
down_revision: str | None = "h8i9j0k1l2m3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# NOTE: pg_trgm extension is already installed in the initial migration.
# Do NOT add CREATE EXTENSION here — it would fail if already exists.


def upgrade() -> None:
    # GIN trigram index on recipe name — enables fast fuzzy search and % operator
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_recipes_name_trgm
        ON recipes USING gin (name gin_trgm_ops)
    """)
    # GIN trigram index on recipe description
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_recipes_description_trgm
        ON recipes USING gin (description gin_trgm_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_recipes_description_trgm")
    op.execute("DROP INDEX IF EXISTS idx_recipes_name_trgm")
