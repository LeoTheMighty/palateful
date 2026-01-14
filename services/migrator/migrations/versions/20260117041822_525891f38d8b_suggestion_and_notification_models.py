"""Suggestion and Notification Models

Revision ID: 525891f38d8b
Revises: 5b51adc124d5
Create Date: 2026-01-17 04:18:22.182458+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '525891f38d8b'
down_revision: Union[str, None] = '5b51adc124d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add notification_preferences and push_tokens to users table
    op.add_column(
        "users",
        sa.Column(
            "notification_preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default='{"push_enabled": true, "email_digest": "daily", "quiet_hours_start": "22:00", "quiet_hours_end": "08:00", "timezone": "America/Denver"}',
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "push_tokens",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="[]",
        ),
    )

    # Add embedding column to recipes table
    op.add_column("recipes", sa.Column("embedding", Vector(384), nullable=True))

    # Create HNSW index for recipe embeddings
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_recipe_embedding_hnsw
        ON recipes USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # Create suggestions table
    op.create_table(
        "suggestions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("suggestion_type", sa.String(50), nullable=False),
        sa.Column("recipe_id", sa.UUID(), nullable=True),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column(
            "trigger_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_dismissed", sa.Boolean(), nullable=False, server_default="false"),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for suggestions
    op.create_index("ix_suggestions_user_id", "suggestions", ["user_id"])
    op.create_index("ix_suggestions_trigger_type", "suggestions", ["trigger_type"])
    op.create_index(
        "ix_suggestions_user_unread",
        "suggestions",
        ["user_id"],
        postgresql_where=sa.text("is_read = false AND is_dismissed = false"),
    )

    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("suggestion_id", sa.UUID(), nullable=True),
        sa.Column("push_token", sa.String(500), nullable=True),
        sa.Column("fcm_message_id", sa.String(255), nullable=True),
        sa.Column("email_address", sa.String(255), nullable=True),
        sa.Column("ses_message_id", sa.String(255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["suggestion_id"], ["suggestions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for notifications
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_channel", "notifications", ["channel"])
    op.create_index("ix_notifications_status", "notifications", ["status"])

    # Create semantic search function for recipes
    op.execute(
        """
        CREATE OR REPLACE FUNCTION search_recipes_semantic(
            query_embedding vector(384),
            user_id UUID,
            similarity_threshold FLOAT DEFAULT 0.5,
            result_limit INT DEFAULT 10
        )
        RETURNS TABLE (
            id UUID,
            name TEXT,
            description TEXT,
            similarity FLOAT
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT r.id, r.name, r.description,
                (1 - (r.embedding <=> query_embedding))::FLOAT as similarity
            FROM recipes r
            JOIN recipe_books rb ON r.recipe_book_id = rb.id
            JOIN recipe_book_users rbu ON rb.id = rbu.recipe_book_id
            WHERE rbu.user_id = search_recipes_semantic.user_id
                AND r.embedding IS NOT NULL
                AND r.archived_at IS NULL
                AND (1 - (r.embedding <=> query_embedding)) > similarity_threshold
            ORDER BY r.embedding <=> query_embedding
            LIMIT result_limit;
        END;
        $$ LANGUAGE plpgsql
        """
    )


def downgrade() -> None:
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS search_recipes_semantic")

    # Drop notifications table
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_channel", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    # Drop suggestions table
    op.drop_index("ix_suggestions_user_unread", table_name="suggestions")
    op.drop_index("ix_suggestions_trigger_type", table_name="suggestions")
    op.drop_index("ix_suggestions_user_id", table_name="suggestions")
    op.drop_table("suggestions")

    # Drop recipe embedding column and index
    op.execute("DROP INDEX IF EXISTS ix_recipe_embedding_hnsw")
    op.drop_column("recipes", "embedding")

    # Drop user notification columns
    op.drop_column("users", "push_tokens")
    op.drop_column("users", "notification_preferences")
