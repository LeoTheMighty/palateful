# Story mcv-7: Flutter — Meal tile in book grid (fork path)

**Status:** ready-for-dev
**Epic:** epic-meals-create-and-view

## Goal

Close the loop: once the Create Meal flow and the Meal detail/edit UX
are live, Leo needs to actually SEE his new Meal tile in the book
grid. This story forks a standalone `MealTile` widget (no subclass of
`_RecipeCard` — epic Decision: RecipeCard), merges recipes and meals
into one sorted grid stream by `updated_at DESC`, and extends the
archived-recipes view to include archived Meals.

## Scope

### Small backend delta

- **`GetRecipeBook.RecipeItem.updated_at`** — the book response's
  recipe rows gain `updated_at` so the Flutter client can merge-sort
  mixed recipe + meal tiles. No behavior change for existing clients
  (additive field).

### Flutter

- **`meal_tile.dart`** (new) — sibling to the private `_RecipeCard`
  in `recipe_book_detail_screen.dart`. Hero is
  `ComponentCollageHero` (reused from mcv-6) built from the
  `MealSummary`'s up-to-4 thumbnails; body is meal name + optional
  description + decorative "N recipes" badge (non-tappable, whole
  tile tap opens `/meals/:id`).
- **`recipe_book_detail_screen.dart`** — modified to:
  - Fetch recipes AND meals in parallel via `Future.wait`. Meals
    failure is non-fatal: a banner above the grid reads "Couldn't
    load meals in this book." and the recipe grid still renders.
  - New `_buildMixedCards` helper merges filtered recipes + meals
    into `_GridEntry` items, sorts by `updated_at DESC`, and emits
    `_RecipeCard` or `MealTile` for each.
  - Header reads "Recipes & Meals (N)" when meals are present,
    "Recipes (N)" otherwise.
  - Empty-state gate now checks both lists.
  - Vibe filter applies to recipes only (meals have no vibe); when
    a filter is active, meals are hidden.
  - Multi-select tap on a `MealTile` is a no-op — meals aren't part
    of the bulk action bar (the bar is recipe-only today).
- **`archived_recipes_screen.dart`** — extended to include archived
  Meals in the same list. Separate row widgets (`_ArchivedRecipeRow`,
  `_ArchivedMealRow`), each with its own Restore button calling
  `_apiClient.restoreRecipe` or `MealService.restoreMeal`.

### Tests

- **`meal_tile_test.dart`** (new, 5 cases) — name + recipes badge,
  2-up / +N collage at 6 components, description rendering, tap
  callback.
- Backend: existing `test_recipe_book::TestGetRecipeBook` tests
  continue to pass because `MockModel` provides a default
  `updated_at`.

## Acceptance Criteria

- [ ] `MealTile` renders with the collage hero, meal name, optional
      description, and "N recipes" badge.
- [ ] Book detail grid fetches recipes AND Meals in parallel; merges
      into one `GridView.count` sorted by `updated_at DESC`.
- [ ] Meals failure renders a non-fatal banner; recipes still render.
- [ ] Tapping a MealTile opens `/meals/:id`.
- [ ] Archived-recipes view includes archived Meals with a Restore
      action that calls `restoreMeal`.
- [ ] Vibe filter active ⇒ meals hidden (vibes don't apply).
- [ ] `dart analyze` on every touched file is clean.
- [ ] `npx nx run api:test` stays green at 100% coverage (one small
      schema addition, no test churn).
- [ ] `flutter test test/features/meals/` + `test/features/
      recipe_books/` stays green.

## File List

New:
- `app/lib/features/meals/widgets/meal_tile.dart`
- `app/test/features/meals/meal_tile_test.dart`

Modified:
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart`
- `app/lib/features/recipes/archived_recipes_screen.dart`
- `services/api/src/api/v1/recipe_book/get_recipe_book.py` —
  `RecipeItem.updated_at` added.

## QA Walkthrough

See `mcv-7-qa-walkthrough.md`.
