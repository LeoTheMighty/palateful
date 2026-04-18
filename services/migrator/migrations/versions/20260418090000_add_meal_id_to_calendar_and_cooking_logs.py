"""Add meal_id to meal_events + meal_recurrence_rules + cooking_logs and source_meal_id to shopping_list_items.

Revision ID: mcal1mealid01
Revises: mcv1mealtables
Create Date: 2026-04-18

Story mcal-1 of epic-meals-calendar. Wires the Meals foundation tables
(from mcv-1) into the calendar surface + shopping list + cooking log.

All changes are additive or nullable-wideningso prod-safe on live rows.
Key invariants:

1. meal_events + meal_recurrence_rules: at most one of
   `recipe_id` / `meal_id` is set on a given row. Both-null is legal
   (free-text event/rule). Constraint created NOT VALID then VALIDATE
   in two statements -- VALIDATE takes SHARE UPDATE EXCLUSIVE, not
   ACCESS EXCLUSIVE, so concurrent reads + writes proceed during the
   scan. Safe on prod-sized tables (O(10k) rows today; validate
   completes in ms).

2. cooking_logs: row is one of three shapes:
   - recipe-only log (`recipe_id` set, `meal_id` NULL, no parent)
   - Meal-level parent log (`meal_id` set, `recipe_id` NULL, no parent)
   - fan-out child log (`recipe_id` set, `meal_id` NULL, `parent_meal_log_id` set)
   `ck_cooking_logs_target` encodes all three in one two-clause CHECK.

3. shopping_list_items.source_meal_id: purely descriptive provenance.
   No constraint vs. recipe_id or meal_event_id -- a row produced by a
   Meal-event add-to-shopping-list path legitimately sets all three.

Downgrade reverses cleanly. `cooking_logs.recipe_id` NOT NULL
restoration is guarded by an assertion that no Meal-level (recipe_id
NULL) rows exist -- raises RuntimeError if they do, so the downgrade
path never silently orphans Meal-level cook history.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "mcal1mealid01"
down_revision: str | None = "mcv1mealtables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ===================================================================
    # 1. meal_events: +meal_id FK + index + XOR check constraint
    # ===================================================================
    op.add_column(
        "meal_events",
        sa.Column(
            "meal_id",
            sa.UUID(),
            sa.ForeignKey("meals.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_meal_events_meal_id", "meal_events", ["meal_id"])
    # NOT VALID: only enforced on new INSERT/UPDATE during this step.
    op.execute(
        "ALTER TABLE meal_events "
        "ADD CONSTRAINT ck_meal_events_recipe_xor_meal "
        "CHECK (num_nonnulls(recipe_id, meal_id) <= 1) NOT VALID"
    )
    # VALIDATE: scans existing rows under SHARE UPDATE EXCLUSIVE (not
    # ACCESS EXCLUSIVE) so reads + writes proceed during the scan.
    op.execute(
        "ALTER TABLE meal_events VALIDATE CONSTRAINT ck_meal_events_recipe_xor_meal"
    )

    # ===================================================================
    # 2. meal_recurrence_rules: parallel treatment
    # ===================================================================
    op.add_column(
        "meal_recurrence_rules",
        sa.Column(
            "meal_id",
            sa.UUID(),
            sa.ForeignKey("meals.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_meal_recurrence_rules_meal_id",
        "meal_recurrence_rules",
        ["meal_id"],
    )
    op.execute(
        "ALTER TABLE meal_recurrence_rules "
        "ADD CONSTRAINT ck_meal_recurrence_rules_recipe_xor_meal "
        "CHECK (num_nonnulls(recipe_id, meal_id) <= 1) NOT VALID"
    )
    op.execute(
        "ALTER TABLE meal_recurrence_rules "
        "VALIDATE CONSTRAINT ck_meal_recurrence_rules_recipe_xor_meal"
    )

    # ===================================================================
    # 3. cooking_logs: recipe_id nullable + meal_id + parent_meal_log_id
    #    + three-shape target check
    # ===================================================================
    op.alter_column(
        "cooking_logs",
        "recipe_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.add_column(
        "cooking_logs",
        sa.Column(
            "meal_id",
            sa.UUID(),
            sa.ForeignKey("meals.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "cooking_logs",
        sa.Column(
            "parent_meal_log_id",
            sa.UUID(),
            sa.ForeignKey("cooking_logs.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    # Three legal shapes encoded in one two-clause CHECK:
    #   (a) exactly one of recipe_id / meal_id set AND no parent
    #   (b) fan-out child: parent set AND recipe_id set AND meal_id NULL
    op.execute(
        "ALTER TABLE cooking_logs "
        "ADD CONSTRAINT ck_cooking_logs_target "
        "CHECK ("
        "  (num_nonnulls(recipe_id, meal_id) = 1) "
        "  OR (parent_meal_log_id IS NOT NULL AND recipe_id IS NOT NULL "
        "      AND meal_id IS NULL)"
        ") NOT VALID"
    )
    op.execute(
        "ALTER TABLE cooking_logs VALIDATE CONSTRAINT ck_cooking_logs_target"
    )

    # ===================================================================
    # 4. shopping_list_items: +source_meal_id (additive, no constraint)
    # ===================================================================
    op.add_column(
        "shopping_list_items",
        sa.Column(
            "source_meal_id",
            sa.UUID(),
            sa.ForeignKey("meals.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # shopping_list_items.source_meal_id (additive drop)
    op.drop_column("shopping_list_items", "source_meal_id")

    # cooking_logs teardown: check if any Meal-level rows exist before
    # restoring NOT NULL on recipe_id. A downgrade that silently
    # orphaned Meal-level cook history would be worse than a failure.
    bind = op.get_bind()
    meal_level_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM cooking_logs WHERE recipe_id IS NULL"
        )
    ).scalar_one()
    if meal_level_count:
        raise RuntimeError(
            f"Cannot downgrade: {meal_level_count} Meal-level cooking_log "
            "row(s) exist (recipe_id NULL). Restoring NOT NULL on "
            "cooking_logs.recipe_id would orphan this data. Delete or "
            "convert Meal-level logs before retrying the downgrade."
        )
    op.drop_constraint("ck_cooking_logs_target", "cooking_logs", type_="check")
    op.drop_column("cooking_logs", "parent_meal_log_id")
    op.drop_column("cooking_logs", "meal_id")
    op.alter_column(
        "cooking_logs",
        "recipe_id",
        existing_type=sa.UUID(),
        nullable=False,
    )

    # meal_recurrence_rules
    op.drop_constraint(
        "ck_meal_recurrence_rules_recipe_xor_meal",
        "meal_recurrence_rules",
        type_="check",
    )
    op.drop_index(
        "ix_meal_recurrence_rules_meal_id", table_name="meal_recurrence_rules"
    )
    op.drop_column("meal_recurrence_rules", "meal_id")

    # meal_events
    op.drop_constraint(
        "ck_meal_events_recipe_xor_meal",
        "meal_events",
        type_="check",
    )
    op.drop_index("ix_meal_events_meal_id", table_name="meal_events")
    op.drop_column("meal_events", "meal_id")
