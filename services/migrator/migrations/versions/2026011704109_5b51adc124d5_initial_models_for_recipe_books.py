"""Initial Models for Recipe Books

Revision ID: 5b51adc124d5
Revises:
Create Date: 2026-01-17 04:10:09.464106+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5b51adc124d5'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable required PostgreSQL extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create users table (UUID ID)
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("auth0_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("picture", sa.String(), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "has_completed_onboarding", sa.Boolean(), nullable=False, server_default="false"
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("auth0_id"),
        sa.UniqueConstraint("email"),
    )

    # Create threads table (UUID ID)
    op.create_table(
        "threads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_threads_user_id", "threads", ["user_id"])

    # Create chats table (UUID ID)
    op.create_table(
        "chats",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("thread_id", sa.UUID(), nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tool_call_id", sa.String(), nullable=True),
        sa.Column("tool_name", sa.String(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
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
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chats_thread_id", "chats", ["thread_id"])

    # Create pantries table (UUID ID)
    op.create_table(
        "pantries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )

    # Create pantry_users table (composite PK)
    op.create_table(
        "pantry_users",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("pantry_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
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
        sa.ForeignKeyConstraint(["pantry_id"], ["pantries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "pantry_id"),
        sa.UniqueConstraint("user_id", "pantry_id", name="uq_pantry_users"),
    )

    # Create recipe_books table (UUID ID)
    op.create_table(
        "recipe_books",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
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
        sa.PrimaryKeyConstraint("id"),
    )

    # Create recipe_book_users table (composite PK)
    op.create_table(
        "recipe_book_users",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("recipe_book_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
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
        sa.ForeignKeyConstraint(["recipe_book_id"], ["recipe_books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "recipe_book_id"),
        sa.UniqueConstraint("user_id", "recipe_book_id", name="uq_recipe_book_users"),
    )

    # Create recipes table (UUID ID)
    op.create_table(
        "recipes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("servings", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("prep_time", sa.Integer(), nullable=True),
        sa.Column("cook_time", sa.Integer(), nullable=True),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("recipe_book_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["recipe_book_id"], ["recipe_books.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create ingredients table (UUID ID)
    op.create_table(
        "ingredients",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("canonical_name", sa.String(), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.String()), nullable=True, server_default="{}"),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column(
            "flavor_profile", postgresql.ARRAY(sa.String()), nullable=True, server_default="{}"
        ),
        sa.Column("default_unit", sa.String(), nullable=True),
        sa.Column("is_canonical", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("pending_review", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("submitted_by_id", sa.UUID(), nullable=True),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
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
        sa.ForeignKeyConstraint(["parent_id"], ["ingredients.id"]),
        sa.ForeignKeyConstraint(["submitted_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_name"),
    )

    # Create ingredient_substitutions table (composite PK)
    op.create_table(
        "ingredient_substitutions",
        sa.Column("ingredient_id", sa.UUID(), nullable=False),
        sa.Column("substitute_id", sa.UUID(), nullable=False),
        sa.Column("context", sa.String(), nullable=True),
        sa.Column("quality", sa.String(), nullable=False),
        sa.Column("ratio", sa.Numeric(5, 2), nullable=False, server_default="1.0"),
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
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["substitute_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ingredient_id", "substitute_id"),
        sa.UniqueConstraint(
            "ingredient_id", "substitute_id", "context", name="uq_ingredient_substitutions"
        ),
    )

    # Create pantry_ingredients table (composite PK)
    op.create_table(
        "pantry_ingredients",
        sa.Column("pantry_id", sa.UUID(), nullable=False),
        sa.Column("ingredient_id", sa.UUID(), nullable=False),
        sa.Column("quantity_display", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit_display", sa.String(), nullable=False),
        sa.Column("quantity_normalized", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit_normalized", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"]),
        sa.ForeignKeyConstraint(["pantry_id"], ["pantries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pantry_id", "ingredient_id"),
        sa.UniqueConstraint("pantry_id", "ingredient_id", name="uq_pantry_ingredients"),
    )

    # Create recipe_ingredients table (composite PK)
    op.create_table(
        "recipe_ingredients",
        sa.Column("recipe_id", sa.UUID(), nullable=False),
        sa.Column("ingredient_id", sa.UUID(), nullable=False),
        sa.Column("quantity_display", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit_display", sa.String(), nullable=False),
        sa.Column("quantity_normalized", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit_normalized", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"]),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("recipe_id", "ingredient_id"),
        sa.UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredients"),
    )

    # Create units table (UUID ID)
    op.create_table(
        "units",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("abbreviation", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("to_base_factor", sa.Numeric(15, 6), nullable=False),
        sa.Column("base_unit", sa.String(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Create cooking_logs table (UUID ID)
    op.create_table(
        "cooking_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scale_factor", sa.Numeric(5, 2), nullable=False, server_default="1.0"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("recipe_id", sa.UUID(), nullable=False),
        sa.Column("pantry_id", sa.UUID(), nullable=False),
        sa.Column(
            "cooked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"]),
        sa.ForeignKeyConstraint(["pantry_id"], ["pantries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create trigram index for fuzzy text search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ingredients_canonical_name_trgm
        ON ingredients USING gin (canonical_name gin_trgm_ops)
    """
    )

    # Create vector index for semantic search (HNSW works on empty tables)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ingredients_embedding
        ON ingredients USING hnsw (embedding vector_cosine_ops)
    """
    )

    # Create fuzzy search function (updated for UUID)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION search_ingredients_fuzzy(
            search_term TEXT,
            similarity_threshold FLOAT DEFAULT 0.3,
            result_limit INT DEFAULT 10
        )
        RETURNS TABLE (
            id UUID, canonical_name TEXT, aliases TEXT[], category TEXT,
            name_similarity FLOAT, alias_similarity FLOAT, best_similarity FLOAT
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                i.id, i.canonical_name, i.aliases, i.category,
                similarity(i.canonical_name, search_term)::FLOAT,
                COALESCE((SELECT MAX(similarity(a, search_term)) FROM unnest(i.aliases) a), 0)::FLOAT,
                GREATEST(
                    similarity(i.canonical_name, search_term),
                    COALESCE((SELECT MAX(similarity(a, search_term)) FROM unnest(i.aliases) a), 0)
                )::FLOAT
            FROM ingredients i
            WHERE i.pending_review = false AND i.archived_at IS NULL AND (
                similarity(i.canonical_name, search_term) > similarity_threshold
                OR EXISTS (SELECT 1 FROM unnest(i.aliases) a WHERE similarity(a, search_term) > similarity_threshold)
            )
            ORDER BY 7 DESC LIMIT result_limit;
        END;
        $$ LANGUAGE plpgsql
    """
    )

    # Create semantic search function (updated for UUID)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION search_ingredients_semantic(
            query_embedding vector(384),
            similarity_threshold FLOAT DEFAULT 0.7,
            result_limit INT DEFAULT 10
        )
        RETURNS TABLE (id UUID, canonical_name TEXT, category TEXT, similarity FLOAT) AS $$
        BEGIN
            RETURN QUERY
            SELECT i.id, i.canonical_name, i.category,
                (1 - (i.embedding <=> query_embedding))::FLOAT
            FROM ingredients i
            WHERE i.embedding IS NOT NULL AND i.pending_review = false AND i.archived_at IS NULL
                AND (1 - (i.embedding <=> query_embedding)) > similarity_threshold
            ORDER BY i.embedding <=> query_embedding
            LIMIT result_limit;
        END;
        $$ LANGUAGE plpgsql
    """
    )


def downgrade() -> None:
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS search_ingredients_semantic")
    op.execute("DROP FUNCTION IF EXISTS search_ingredients_fuzzy")

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_ingredients_embedding")
    op.execute("DROP INDEX IF EXISTS idx_ingredients_canonical_name_trgm")

    # Drop tables in reverse order
    op.drop_table("cooking_logs")
    op.drop_table("units")
    op.drop_table("recipe_ingredients")
    op.drop_table("pantry_ingredients")
    op.drop_table("ingredient_substitutions")
    op.drop_table("ingredients")
    op.drop_table("recipes")
    op.drop_table("recipe_book_users")
    op.drop_table("recipe_books")
    op.drop_table("pantry_users")
    op.drop_table("pantries")
    op.drop_table("chats")
    op.drop_table("threads")
    op.drop_table("users")

    # Extensions are shared, don't drop them
