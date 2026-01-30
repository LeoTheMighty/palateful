"""Add shared shopping cart system

Revision ID: a1b2c3d4e5f6
Revises: 9c4d5e6f7a8b
Create Date: 2026-01-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9c4d5e6f7a8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create shopping_list_users table (join table for sharing)
    op.create_table(
        "shopping_list_users",
        sa.Column("shopping_list_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="editor"),
        sa.Column("notify_on_add", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_on_check", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notify_on_deadline", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("shopping_list_id", "user_id"),
        sa.ForeignKeyConstraint(
            ["shopping_list_id"], ["shopping_lists.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "shopping_list_id", "user_id", name="uq_shopping_list_users"
        ),
    )

    # 2. Add sharing columns to shopping_lists
    op.add_column(
        "shopping_lists",
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "shopping_lists",
        sa.Column("share_code", sa.String(10), nullable=True),
    )
    op.add_column(
        "shopping_lists",
        sa.Column("default_deadline", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shopping_lists",
        sa.Column(
            "auto_populate_from_calendar",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "shopping_lists",
        sa.Column(
            "calendar_lookahead_days", sa.Integer(), nullable=False, server_default="7"
        ),
    )
    op.add_column(
        "shopping_lists",
        sa.Column("widget_color", sa.String(7), nullable=True),
    )
    op.add_column(
        "shopping_lists",
        sa.Column("sort_by", sa.String(20), nullable=False, server_default="'deadline'"),
    )
    op.create_index(
        "ix_shopping_lists_share_code", "shopping_lists", ["share_code"], unique=True
    )

    # 3. Add deadline/collaboration columns to shopping_list_items
    op.add_column(
        "shopping_list_items",
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shopping_list_items",
        sa.Column("meal_event_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "shopping_list_items",
        sa.Column("due_reason", sa.String(100), nullable=True),
    )
    op.add_column(
        "shopping_list_items",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "shopping_list_items",
        sa.Column("added_by_user_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "shopping_list_items",
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "shopping_list_items",
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shopping_list_items",
        sa.Column("assigned_to_user_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "shopping_list_items",
        sa.Column("store_section", sa.String(50), nullable=True),
    )
    op.add_column(
        "shopping_list_items",
        sa.Column("store_order", sa.Integer(), nullable=True),
    )

    # 4. Add foreign keys for new item columns
    op.create_foreign_key(
        "fk_shopping_list_items_meal_event",
        "shopping_list_items",
        "meal_events",
        ["meal_event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_shopping_list_items_added_by",
        "shopping_list_items",
        "users",
        ["added_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_shopping_list_items_assigned_to",
        "shopping_list_items",
        "users",
        ["assigned_to_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 5. Create indexes for common queries on items
    op.create_index(
        "ix_shopping_list_items_due_at", "shopping_list_items", ["due_at"]
    )
    op.create_index(
        "ix_shopping_list_items_meal_event_id", "shopping_list_items", ["meal_event_id"]
    )

    # 6. Create shopping_list_events table (activity feed)
    op.create_table(
        "shopping_list_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column(
            "event_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("shopping_list_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["shopping_list_id"], ["shopping_lists.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_shopping_list_events_list_sequence",
        "shopping_list_events",
        ["shopping_list_id", "sequence"],
    )


def downgrade() -> None:
    # Drop shopping_list_events table
    op.drop_index(
        "ix_shopping_list_events_list_sequence", table_name="shopping_list_events"
    )
    op.drop_table("shopping_list_events")

    # Drop indexes on shopping_list_items
    op.drop_index("ix_shopping_list_items_meal_event_id", table_name="shopping_list_items")
    op.drop_index("ix_shopping_list_items_due_at", table_name="shopping_list_items")

    # Drop foreign keys on shopping_list_items
    op.drop_constraint(
        "fk_shopping_list_items_assigned_to", "shopping_list_items", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_shopping_list_items_added_by", "shopping_list_items", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_shopping_list_items_meal_event", "shopping_list_items", type_="foreignkey"
    )

    # Drop columns from shopping_list_items
    op.drop_column("shopping_list_items", "store_order")
    op.drop_column("shopping_list_items", "store_section")
    op.drop_column("shopping_list_items", "assigned_to_user_id")
    op.drop_column("shopping_list_items", "checked_at")
    op.drop_column("shopping_list_items", "notes")
    op.drop_column("shopping_list_items", "added_by_user_id")
    op.drop_column("shopping_list_items", "priority")
    op.drop_column("shopping_list_items", "due_reason")
    op.drop_column("shopping_list_items", "meal_event_id")
    op.drop_column("shopping_list_items", "due_at")

    # Drop index and columns from shopping_lists
    op.drop_index("ix_shopping_lists_share_code", table_name="shopping_lists")
    op.drop_column("shopping_lists", "sort_by")
    op.drop_column("shopping_lists", "widget_color")
    op.drop_column("shopping_lists", "calendar_lookahead_days")
    op.drop_column("shopping_lists", "auto_populate_from_calendar")
    op.drop_column("shopping_lists", "default_deadline")
    op.drop_column("shopping_lists", "share_code")
    op.drop_column("shopping_lists", "is_shared")

    # Drop shopping_list_users table
    op.drop_table("shopping_list_users")
