"""Add calendar and meal planning models

Revision ID: 8b3c4d5e6f7a
Revises: 7a2d3e4f5b6c
Create Date: 2026-01-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8b3c4d5e6f7a"
down_revision: Union[str, None] = "7a2d3e4f5b6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create meal_events table
    op.create_table(
        "meal_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meal_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("notify_prep_start", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("prep_start_offset_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("notify_cook_start", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("cook_start_offset_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("recurrence_rule", sa.String(100), nullable=True),
        sa.Column("recurrence_end_date", sa.Date(), nullable=True),
        sa.Column("parent_event_id", sa.UUID(), nullable=True),
        sa.Column("recipe_id", sa.UUID(), nullable=True),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("pantry_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pantry_id"], ["pantries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_event_id"], ["meal_events.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_meal_events_owner_id", "meal_events", ["owner_id"])
    op.create_index("ix_meal_events_scheduled_at", "meal_events", ["scheduled_at"])
    op.create_index("ix_meal_events_status", "meal_events", ["status"])

    # Create meal_event_participants table (composite PK)
    op.create_table(
        "meal_event_participants",
        sa.Column("meal_event_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="invited"),
        sa.Column("role", sa.String(20), nullable=False, server_default="guest"),
        sa.Column("assigned_tasks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.PrimaryKeyConstraint("meal_event_id", "user_id"),
        sa.ForeignKeyConstraint(["meal_event_id"], ["meal_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("meal_event_id", "user_id", name="uq_meal_event_participants"),
    )

    # Create recipe_steps table
    op.create_table(
        "recipe_steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("active_time_minutes", sa.Integer(), nullable=True),
        sa.Column("timers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("wait_time_minutes", sa.Integer(), nullable=True),
        sa.Column("wait_type", sa.Text(), nullable=True),
        sa.Column("wait_min_minutes", sa.Integer(), nullable=True),
        sa.Column("wait_max_minutes", sa.Integer(), nullable=True),
        sa.Column("can_prep_ahead", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("recipe_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_recipe_steps_recipe_id", "recipe_steps", ["recipe_id"])

    # Create prep_steps table
    op.create_table(
        "prep_steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("active_time_minutes", sa.Integer(), nullable=True),
        sa.Column("wait_time_minutes", sa.Integer(), nullable=True),
        sa.Column("wait_type", sa.String(50), nullable=True),
        sa.Column("can_prep_ahead", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("max_prep_ahead_hours", sa.Integer(), nullable=True),
        sa.Column("notify_when_done", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wait_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meal_event_id", sa.UUID(), nullable=True),
        sa.Column("recipe_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["meal_event_id"], ["meal_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_prep_steps_meal_event_id", "prep_steps", ["meal_event_id"])

    # Create shopping_lists table
    op.create_table(
        "shopping_lists",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("meal_event_id", sa.UUID(), nullable=True),
        sa.Column("pantry_id", sa.UUID(), nullable=True),
        sa.Column("owner_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["meal_event_id"], ["meal_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pantry_id"], ["pantries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_shopping_lists_owner_id", "shopping_lists", ["owner_id"])

    # Create shopping_list_items table
    op.create_table(
        "shopping_list_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("is_checked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("checked_by_user_id", sa.UUID(), nullable=True),
        sa.Column("recipe_id", sa.UUID(), nullable=True),
        sa.Column("already_have_quantity", sa.Numeric(10, 2), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("shopping_list_id", sa.UUID(), nullable=False),
        sa.Column("ingredient_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["shopping_list_id"], ["shopping_lists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["checked_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_shopping_list_items_shopping_list_id", "shopping_list_items", ["shopping_list_id"])

    # Create active_timers table
    op.create_table(
        "active_timers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_when_paused", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notify_on_complete", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notification_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("meal_event_id", sa.UUID(), nullable=True),
        sa.Column("recipe_step_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["meal_event_id"], ["meal_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_step_id"], ["recipe_steps.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_active_timers_user_id", "active_timers", ["user_id"])
    op.create_index("ix_active_timers_status", "active_timers", ["status"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index("ix_active_timers_status", table_name="active_timers")
    op.drop_index("ix_active_timers_user_id", table_name="active_timers")
    op.drop_table("active_timers")

    op.drop_index("ix_shopping_list_items_shopping_list_id", table_name="shopping_list_items")
    op.drop_table("shopping_list_items")

    op.drop_index("ix_shopping_lists_owner_id", table_name="shopping_lists")
    op.drop_table("shopping_lists")

    op.drop_index("ix_prep_steps_meal_event_id", table_name="prep_steps")
    op.drop_table("prep_steps")

    op.drop_index("ix_recipe_steps_recipe_id", table_name="recipe_steps")
    op.drop_table("recipe_steps")

    op.drop_table("meal_event_participants")

    op.drop_index("ix_meal_events_status", table_name="meal_events")
    op.drop_index("ix_meal_events_scheduled_at", table_name="meal_events")
    op.drop_index("ix_meal_events_owner_id", table_name="meal_events")
    op.drop_table("meal_events")
