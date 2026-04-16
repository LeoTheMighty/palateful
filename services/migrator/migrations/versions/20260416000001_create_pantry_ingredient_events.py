"""Create pantry_ingredient_events audit table

Revision ID: f1p2t3r4y5e6
Revises: e1p2t3r4y5a6
Create Date: 2026-04-16

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1p2t3r4y5e6"
down_revision: str | None = "e1p2t3r4y5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pantry_ingredient_events",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
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
        sa.Column(
            "pantry_id",
            sa.UUID(),
            sa.ForeignKey("pantries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ingredient_id",
            sa.UUID(),
            sa.ForeignKey("ingredients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("delta_quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column(
            "source_meal_event_id",
            sa.UUID(),
            sa.ForeignKey("meal_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_pantry_ingredient_events_pantry_id",
        "pantry_ingredient_events",
        ["pantry_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pantry_ingredient_events_pantry_id",
        table_name="pantry_ingredient_events",
    )
    op.drop_table("pantry_ingredient_events")
