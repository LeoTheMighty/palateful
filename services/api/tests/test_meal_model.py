"""Tests for Meal / MealRecipe / MealFavorite models.

Introspection-only — the project test infra is mock-backed, so the
real-DB cascade/RESTRICT behavior is verified by the migration round-trip
in CI (`npx nx run migrator:check-models`). These tests guard against
future ORM drift that would silently lose those invariants.
"""

from sqlalchemy import inspect

from utils.models.meal import Meal
from utils.models.meal_favorite import MealFavorite
from utils.models.meal_recipe import MealRecipe


def _fk_by_column(model, column_name: str):
    """Return the ForeignKey for `column_name` on `model`, or None."""
    col = getattr(model, column_name).property.columns[0]
    for fk in col.foreign_keys:
        return fk
    return None


class TestMealModel:
    def test_tablename(self):
        assert Meal.__tablename__ == "meals"

    def test_book_fk_cascades(self):
        fk = _fk_by_column(Meal, "recipe_book_id")
        assert fk is not None
        assert fk.ondelete == "CASCADE"
        assert fk.column.table.name == "recipe_books"

    def test_name_column_is_required(self):
        col = Meal.name.property.columns[0]
        assert col.nullable is False

    def test_share_token_is_nullable(self):
        col = Meal.share_token.property.columns[0]
        assert col.nullable is True

    def test_share_token_partial_unique_index_declared(self):
        index_names = {ix.name for ix in Meal.__table__.indexes}
        assert "ix_meals_share_token" in index_names
        # pull the index and check it's unique + has a partial clause
        share_ix = next(
            ix for ix in Meal.__table__.indexes if ix.name == "ix_meals_share_token"
        )
        assert share_ix.unique is True
        assert share_ix.dialect_options["postgresql"]["where"] is not None

    def test_components_relationship_cascades(self):
        rel = inspect(Meal).relationships["components"]
        assert rel.cascade.delete_orphan is True
        assert rel.cascade.delete is True

    def test_recipe_book_id_is_indexed(self):
        index_names = {ix.name for ix in Meal.__table__.indexes}
        assert "ix_meals_recipe_book_id" in index_names


class TestMealRecipeModel:
    def test_tablename(self):
        assert MealRecipe.__tablename__ == "meal_recipes"

    def test_meal_fk_cascades(self):
        fk = _fk_by_column(MealRecipe, "meal_id")
        assert fk is not None
        assert fk.ondelete == "CASCADE"

    def test_recipe_fk_restricts(self):
        """RESTRICT is the headline invariant — meal must not silently orphan."""
        fk = _fk_by_column(MealRecipe, "recipe_id")
        assert fk is not None
        assert fk.ondelete == "RESTRICT"

    def test_composite_primary_key(self):
        pk_cols = {col.name for col in MealRecipe.__table__.primary_key.columns}
        assert pk_cols == {"meal_id", "recipe_id"}

    def test_order_index_defaults_to_zero(self):
        col = MealRecipe.order_index.property.columns[0]
        assert col.nullable is False
        # server default surfaces as a TextClause
        assert col.server_default is not None

    def test_recipe_id_indexed(self):
        index_names = {ix.name for ix in MealRecipe.__table__.indexes}
        assert "ix_meal_recipes_recipe_id" in index_names


class TestMealFavoriteModel:
    def test_tablename(self):
        assert MealFavorite.__tablename__ == "meal_favorites"

    def test_user_fk_cascades(self):
        fk = _fk_by_column(MealFavorite, "user_id")
        assert fk is not None
        assert fk.ondelete == "CASCADE"

    def test_meal_fk_cascades(self):
        fk = _fk_by_column(MealFavorite, "meal_id")
        assert fk is not None
        assert fk.ondelete == "CASCADE"

    def test_composite_primary_key(self):
        pk_cols = {col.name for col in MealFavorite.__table__.primary_key.columns}
        assert pk_cols == {"user_id", "meal_id"}

    def test_meal_id_indexed(self):
        index_names = {ix.name for ix in MealFavorite.__table__.indexes}
        assert "ix_meal_favorites_meal_id" in index_names


class TestModelRegistration:
    def test_models_exported_from_package(self):
        from utils import models

        assert models.Meal is Meal
        assert models.MealRecipe is MealRecipe
        assert models.MealFavorite is MealFavorite

    def test_models_in_all(self):
        from utils.models import __all__

        assert "Meal" in __all__
        assert "MealRecipe" in __all__
        assert "MealFavorite" in __all__
