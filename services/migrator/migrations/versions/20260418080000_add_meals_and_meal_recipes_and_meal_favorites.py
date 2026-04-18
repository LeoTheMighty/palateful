"""Add meals + meal_recipes + meal_favorites.

Revision ID: mcv1mealtables
Revises: sbf3s3keycol0
Create Date: 2026-04-18

Story mcv-1 of epic-meals-create-and-view. Greenfield tables — no
existing rows, no backfill. Three tables land in one transaction:

1. `meals` — reusable named grouping; scoped to a recipe_book, inherits
   sharing via that FK. `share_token` column exists but no endpoint in
   this epic touches it (the sharing-and-ai epic owns reads/writes; we
   pay the schema cost now so there's no second migration).
2. `meal_recipes` — ordered join. `recipe_id` is `ondelete RESTRICT`
   deliberately: user-facing deletes are soft archives, so the hard
   delete path should only ever come from admin scripts or tests.
   RESTRICT turns a silent orphaning bug into a loud IntegrityError.
3. `meal_favorites` — per-user pinning, parallels user_favorites.

No touches to meal_events or meal_recurrence_rules — those gain meal_id
columns in the calendar epic, which chains off this migration.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "mcv1mealtables"
down_revision: str | None = "sbf3s3keycol0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -------- meals --------
    op.create_table(
        "meals",
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
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "recipe_book_id",
            sa.UUID(),
            sa.ForeignKey("recipe_books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("share_token", sa.String(20), nullable=True),
    )
    op.create_index("ix_meals_recipe_book_id", "meals", ["recipe_book_id"])
    # Partial unique: only rows with a token are uniqueness-checked, so
    # the NULL majority stays cheap. Sharing epic flips this on when it
    # starts minting tokens.
    op.create_index(
        "ix_meals_share_token",
        "meals",
        ["share_token"],
        unique=True,
        postgresql_where=sa.text("share_token IS NOT NULL"),
    )

    # -------- meal_recipes --------
    op.create_table(
        "meal_recipes",
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
            "meal_id",
            sa.UUID(),
            sa.ForeignKey("meals.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "recipe_id",
            sa.UUID(),
            # RESTRICT is intentional — see module docstring.
            sa.ForeignKey("recipes.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index("ix_meal_recipes_recipe_id", "meal_recipes", ["recipe_id"])

    # -------- meal_favorites --------
    op.create_table(
        "meal_favorites",
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
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "meal_id",
            sa.UUID(),
            sa.ForeignKey("meals.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index("ix_meal_favorites_meal_id", "meal_favorites", ["meal_id"])


def downgrade() -> None:
    # Reverse order — favorites depend on meals, meal_recipes depend on
    # both meals and recipes.
    op.drop_index("ix_meal_favorites_meal_id", table_name="meal_favorites")
    op.drop_table("meal_favorites")

    op.drop_index("ix_meal_recipes_recipe_id", table_name="meal_recipes")
    op.drop_table("meal_recipes")

    op.drop_index("ix_meals_share_token", table_name="meals")
    op.drop_index("ix_meals_recipe_book_id", table_name="meals")
    op.drop_table("meals")
