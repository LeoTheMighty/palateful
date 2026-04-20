"""Drop ingredient canonicalization infrastructure.

Revision ID: singdrop4
Revises: efi3infrfields1
Create Date: 2026-04-20

Story str-ing-4 of epic-ingredients-string-simplification. Retires every
schema object that exists only to support cross-recipe ingredient identity
/ matching / pantry-check:

Dropped tables:
  - `ingredient_substitutions` (substitution graph — empty in prod).
  - `ingredient_matches` (matcher cache — populated by the retired
    MatchIngredientsTask).

Dropped indexes:
  - `idx_ingredients_canonical_name_trgm` (pg_trgm GIN).
  - `idx_ingredients_embedding` (pgvector HNSW).

Dropped constraint:
  - `ingredients_canonical_name_key` (unique constraint from
    `unique=True` on canonical_name).

Dropped function:
  - `search_ingredients_fuzzy(text)` PL/pgSQL.

Dropped columns on `ingredients`:
  - `embedding` (Vector(384)).
  - `parent_id` (self-FK; FK constraint dropped first).
  - `pending_review` (review-queue flag).
  - `is_canonical` (canonical/pending dichotomy retired).
  - `aliases` (ARRAY synonym list).
  - `category` (per-ingredient display category — handlers pass None in
    str-ing-2; the per-row display value was never read at serving time).

Retained — by design, not oversight:
  - `shopping_list_items.already_have_quantity` — NULL placeholder for a
    future pantry-check revival. See ShoppingListItem model comment.
  - `ingredients.submitted_by_id` FK — audit trail.

Deploy ordering:
  str-ing-2 + str-ing-3 must be in prod before this migration lands so
  runtime code stops reading the dropped columns. After this migration
  ships, the schema is strictly smaller; no code path targets the removed
  objects.

Down-migration re-creates the dropped objects as empty columns / tables /
indexes / function stub. Data populated pre-migration is NOT restored —
dogfood-only regime accepts this (per epic §Risks).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "singdrop4"
down_revision: str | None = "efi3infrfields1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Empty the substitutions table first (no-op in prod; safety).
    op.execute("TRUNCATE TABLE ingredient_substitutions")

    # 2. Drop dependent tables before touching columns on `ingredients`.
    op.drop_table("ingredient_substitutions")
    op.drop_table("ingredient_matches")

    # 3. Drop the PL/pgSQL fuzzy-search function.
    op.execute("DROP FUNCTION IF EXISTS search_ingredients_fuzzy(text)")

    # 4. Drop indexes on `ingredients` that only serve the retired
    #    matcher / embedding paths. Names are `idx_` (not `ix_`).
    op.drop_index("idx_ingredients_embedding", table_name="ingredients")
    op.drop_index("idx_ingredients_canonical_name_trgm", table_name="ingredients")

    # 5. Drop the unique constraint on canonical_name (auto-named). With
    #    cross-recipe identity retired, duplicate names are expected.
    op.drop_constraint(
        "ingredients_canonical_name_key", "ingredients", type_="unique"
    )

    # 6. Drop the self-FK on parent_id before the column itself. The FK
    #    carries Postgres' auto-generated name
    #    `ingredients_parent_id_fkey`.
    op.drop_constraint(
        "ingredients_parent_id_fkey", "ingredients", type_="foreignkey"
    )

    # 7. Drop the columns that only existed to power canonicalization /
    #    matching / pending-review / category. `category` is retired here
    #    (str-ing-2 already stopped every handler from reading it).
    op.drop_column("ingredients", "embedding")
    op.drop_column("ingredients", "parent_id")
    op.drop_column("ingredients", "pending_review")
    op.drop_column("ingredients", "is_canonical")
    op.drop_column("ingredients", "aliases")
    op.drop_column("ingredients", "category")


def downgrade() -> None:
    """Re-create the dropped objects as empty.

    Data is NOT restored — down recreates columns as NULL / empty tables.
    Restoring is a per-row manual step if ever needed; not attempted by
    the migration.
    """
    # 1. Re-add dropped columns on `ingredients`.
    op.add_column(
        "ingredients",
        sa.Column(
            "category",
            sa.String(),
            nullable=True,
        ),
    )
    op.add_column(
        "ingredients",
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.String()),
            nullable=True,
            server_default="{}",
        ),
    )
    op.add_column(
        "ingredients",
        sa.Column(
            "is_canonical",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "ingredients",
        sa.Column(
            "pending_review",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "ingredients",
        sa.Column("parent_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "ingredients",
        sa.Column("embedding", Vector(384), nullable=True),
    )

    # 2. Re-add the self-FK.
    op.create_foreign_key(
        "ingredients_parent_id_fkey",
        "ingredients",
        "ingredients",
        ["parent_id"],
        ["id"],
    )

    # 3. Re-add the unique constraint.
    op.create_unique_constraint(
        "ingredients_canonical_name_key", "ingredients", ["canonical_name"]
    )

    # 4. Re-create the indexes. The HNSW index depends on the embedding
    #    column we just re-added.
    op.execute(
        """
        CREATE INDEX idx_ingredients_canonical_name_trgm
            ON ingredients
         USING gin (canonical_name gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_ingredients_embedding
            ON ingredients
         USING hnsw (embedding vector_cosine_ops)
        """
    )

    # 5. Re-create the PL/pgSQL function as an empty stub. Callers would
    #    need to restore the original body from git history if they need
    #    the fuzzy-match behavior back.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION search_ingredients_fuzzy(
            q text
        ) RETURNS TABLE (
            id uuid, canonical_name text, category text, similarity real
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT i.id, i.canonical_name, i.category,
                   similarity(i.canonical_name, q) AS similarity
              FROM ingredients i
             WHERE i.canonical_name % q
             ORDER BY similarity DESC
             LIMIT 10;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # 6. Re-create `ingredient_matches`.
    op.create_table(
        "ingredient_matches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_text_normalized", sa.Text(), nullable=False),
        sa.Column("matched_ingredient_id", sa.UUID(), nullable=True),
        sa.Column("match_type", sa.String(length=20), nullable=False),
        sa.Column(
            "confidence", sa.Float(), nullable=False, server_default="1.0"
        ),
        sa.Column("user_confirmed", sa.Boolean(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["matched_ingredient_id"], ["ingredients.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingredient_matches_source_text_normalized",
        "ingredient_matches",
        ["source_text_normalized"],
    )
    op.create_index(
        "ix_ingredient_matches_user_confirmed",
        "ingredient_matches",
        ["user_confirmed"],
    )

    # 7. Re-create `ingredient_substitutions`.
    op.create_table(
        "ingredient_substitutions",
        sa.Column("ingredient_id", sa.UUID(), nullable=False),
        sa.Column("substitute_id", sa.UUID(), nullable=False),
        sa.Column("context", sa.String(), nullable=True),
        sa.Column("quality", sa.String(), nullable=False),
        sa.Column(
            "ratio", sa.Numeric(5, 2), nullable=False, server_default="1.0"
        ),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["substitute_id"], ["ingredients.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("ingredient_id", "substitute_id"),
        sa.UniqueConstraint(
            "ingredient_id",
            "substitute_id",
            "context",
            name="uq_ingredient_substitutions",
        ),
    )
