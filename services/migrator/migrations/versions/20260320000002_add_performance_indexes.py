"""Add performance indexes for frequently queried columns

Revision ID: n4o5p6q7r8s9
Revises: l2m3n4o5p6q7
Create Date: 2026-03-20

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n4o5p6q7r8s9"
down_revision: str | None = "l2m3n4o5p6q7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # recipe_book_users.user_id — used in every access control check
    op.create_index("ix_recipe_book_users_user_id", "recipe_book_users", ["user_id"])

    # recipe_ingredients.ingredient_id — used in search, shopping list populate
    op.create_index("ix_recipe_ingredients_ingredient_id", "recipe_ingredients", ["ingredient_id"])

    # recipes.recipe_book_id — used in list/search/access checks
    op.create_index("ix_recipes_recipe_book_id", "recipes", ["recipe_book_id"])

    # shopping_list_items.ingredient_id — used in populate logic dedup
    op.create_index("ix_shopping_list_items_ingredient_id", "shopping_list_items", ["ingredient_id"])


def downgrade() -> None:
    op.drop_index("ix_shopping_list_items_ingredient_id", table_name="shopping_list_items")
    op.drop_index("ix_recipes_recipe_book_id", table_name="recipes")
    op.drop_index("ix_recipe_ingredients_ingredient_id", table_name="recipe_ingredients")
    op.drop_index("ix_recipe_book_users_user_id", table_name="recipe_book_users")
