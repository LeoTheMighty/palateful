"""Create meal_recurrence_rules table + FK on meal_events.

Revision ID: a1r2e3c4u5r6
Revises: f1p2t3r4y5e6
Create Date: 2026-04-17

Adds a slot-based recurrence rule table and a nullable FK on meal_events
(recurrence_rule_id, ON DELETE SET NULL). Includes a unique index on
(recurrence_rule_id, scheduled_at) for idempotent materialization under
concurrency.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1r2e3c4u5r6"
down_revision: str | None = "b1s2l3p4q5r6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meal_recurrence_rules",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column(
            "recipe_id",
            sa.UUID(),
            sa.ForeignKey("recipes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("meal_type", sa.String(20), nullable=False),
        sa.Column(
            "weekdays",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column("interval", sa.String(20), nullable=False),
        sa.Column("monthly_nth", sa.String(10), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("tz_name", sa.String(64), nullable=False),
        sa.Column(
            "is_shared",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("materialized_through", sa.Date(), nullable=True),
    )

    op.create_index(
        "ix_meal_recurrence_rules_owner_id",
        "meal_recurrence_rules",
        ["owner_id"],
    )
    op.create_index(
        "ix_meal_recurrence_rules_materialized_through",
        "meal_recurrence_rules",
        ["materialized_through"],
    )

    op.add_column(
        "meal_events",
        sa.Column(
            "recurrence_rule_id",
            sa.UUID(),
            sa.ForeignKey("meal_recurrence_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_meal_events_recurrence_rule_id",
        "meal_events",
        ["recurrence_rule_id"],
    )
    # Unique partial index: idempotent materialization under concurrency.
    # Only applies when recurrence_rule_id IS NOT NULL so manual (non-rule)
    # events are unaffected.
    op.create_index(
        "uq_meal_events_rule_scheduled_at",
        "meal_events",
        ["recurrence_rule_id", "scheduled_at"],
        unique=True,
        postgresql_where=sa.text("recurrence_rule_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_meal_events_rule_scheduled_at",
        table_name="meal_events",
    )
    op.drop_index(
        "ix_meal_events_recurrence_rule_id",
        table_name="meal_events",
    )
    op.drop_column("meal_events", "recurrence_rule_id")
    op.drop_index(
        "ix_meal_recurrence_rules_materialized_through",
        table_name="meal_recurrence_rules",
    )
    op.drop_index(
        "ix_meal_recurrence_rules_owner_id",
        table_name="meal_recurrence_rules",
    )
    op.drop_table("meal_recurrence_rules")
