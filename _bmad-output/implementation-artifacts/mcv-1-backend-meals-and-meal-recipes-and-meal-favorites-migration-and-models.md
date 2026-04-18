# Story mcv-1: Backend — meals + meal_recipes + meal_favorites migration and models

**Status:** done
**Epic:** epic-meals-create-and-view

## Goal

Land the greenfield DB schema that every subsequent mcv-* story hangs off:

1. `meals` — Leo's named grouping of 2+ recipes, scoped to a recipe_book.
2. `meal_recipes` — ordered join from Meal → Recipe, `ondelete RESTRICT`
   so the ORM can never silently orphan a Meal by hard-deleting a recipe.
3. `meal_favorites` — parallels `user_favorites` for per-user pinning.

No calendar or shopping-list wiring; `share_token` column exists but no
handler reads it in this epic (the sharing epic owns the read path).

## Scope

### New SQLAlchemy models (`libraries/utils/utils/models/`)

- `meal.py` — `Meal(Base)` with `name / description / recipe_book_id /
  share_token / archived_at / timestamps`. Partial unique index on
  `share_token WHERE share_token IS NOT NULL` via `__table_args__`.
  Relationship: `components: list[MealRecipe]`, `cascade="all, delete-
  orphan"`, `order_by="MealRecipe.order_index"`.
- `meal_recipe.py` — `MealRecipe(JoinsBase)` composite PK `(meal_id,
  recipe_id)`. `meal_id` FK cascades from meals; `recipe_id` FK is
  `ondelete RESTRICT` so the DB rejects accidental hard-deletes. Secondary
  index on `recipe_id`. `order_index` int not null default 0.
- `meal_favorite.py` — `MealFavorite(JoinsBase)` composite PK
  `(user_id, meal_id)`, both sides cascade. Parallel favorites table
  (no polymorphic unification with `user_favorites` — decided in the
  epic).

`__init__.py` registers all three in both the imports and `__all__`.

### Migration

`services/migrator/migrations/versions/20260418080000_add_meals_and_meal_recipes_and_meal_favorites.py`
- `down_revision = "sbf3s3keycol0"` (chains off the most recent head:
  sbf-3 add_import_item_s3_key).
- `upgrade()` creates three tables + indexes in one transaction. No
  backfill — zero existing rows.
- `downgrade()` drops them in reverse order (favorites → recipes → meals)
  so FK dependencies resolve cleanly.

### Tests

`services/api/tests/test_meal_model.py` — introspection-based since the
project test infra is mock-backed (no live DB):
- Imports all three models without error.
- Asserts `Meal.components` relationship exists with cascade="all,
  delete-orphan".
- Asserts `MealRecipe.recipe_id` FK has `ondelete="RESTRICT"`.
- Asserts `MealRecipe.meal_id` FK has `ondelete="CASCADE"`.
- Asserts `meal_favorites` has composite PK and both FKs cascade.
- Asserts `Meal.share_token` is nullable + the partial unique index is
  declared via __table_args__.

Real-DB cascade verification runs in CI via `alembic check` + the
round-trip migration smoke test (migrate → downgrade → migrate).

## Acceptance Criteria

- [x] Three new models land; `from utils.models import Meal,
      MealRecipe, MealFavorite` resolves.
- [x] Migration `20260418080000_add_meals_and_meal_recipes_and_meal_favorites.py`
      creates the three tables + indexes (ix_meals_recipe_book_id,
      ix_meals_share_token partial unique, ix_meal_recipes_recipe_id,
      ix_meal_favorites_meal_id).
- [x] `upgrade()` and `downgrade()` are both reversible on a fresh DB.
- [x] `npx nx run migrator:check-models` passes — ORM agrees with DB.
- [x] `test_meal_model.py` passes.
- [x] No changes to `meal_events` or `meal_recurrence_rules` — calendar
      epic owns those columns.

## QA Walkthrough

See `mcv-1-qa-walkthrough.md`.

## File List

- `libraries/utils/utils/models/meal.py` (new)
- `libraries/utils/utils/models/meal_recipe.py` (new)
- `libraries/utils/utils/models/meal_favorite.py` (new)
- `libraries/utils/utils/models/__init__.py` (modified — register)
- `services/migrator/migrations/versions/20260418080000_add_meals_and_meal_recipes_and_meal_favorites.py` (new)
- `services/api/tests/test_meal_model.py` (new)
