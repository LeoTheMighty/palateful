"""Add recipes.inferred_fields JSONB column.

Revision ID: efi3infrfields1
Revises: abi2bsoftarch1
Create Date: 2026-04-20

Story efi-3 of epic-extractor-field-inference. Adds a JSONB column
``recipes.inferred_fields`` that carries the list of recipe-root fields
the extractor best-guessed (from ``INFERABLE_FIELDS``). Populated by
``create_recipe_task`` when finalizing an import, surfaced by
``GetRecipe`` + ``UpdateRecipe``.

Safety rails:

1. NOT NULL with server-side default ``'[]'::jsonb`` — historical rows
   get an empty list automatically, no backfill needed.
2. Additive column on a small-to-medium table; no lock contention
   concerns at current scale. Single-statement DDL, default-value rewrite
   is bounded by row count.
3. Downgrade drops the column cleanly (no FK, no index).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "efi3infrfields1"
down_revision: str | None = "abi2bsoftarch1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column(
            "inferred_fields",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("recipes", "inferred_fields")
