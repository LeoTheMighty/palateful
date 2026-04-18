# Story mcv-6: Flutter — Meal detail + edit screens

**Status:** ready-for-dev
**Epic:** epic-meals-create-and-view

## Goal

Replace the mcv-4 placeholder bodies on `meal_detail_screen.dart` and
`meal_edit_screen.dart` with the real Meal UX: ComponentCollageHero,
action bar (Favorite live, Plan/Shopping/Share disabled-with-tooltip,
Archive + Edit live), ComponentRow list, drag-to-reorder, Add Recipe
FAB, swipe-to-delete with ≥2 guard.

## Scope

### Small backend delta

- **`MealResponse.is_favorite: bool = False`** — the Meal detail needs
  initial favorite state. Without it, the Favorite action button can't
  reflect the current state (only optimistic post-tap). Small addition;
  wires through `MealService.is_favorited(user_id, meal_id)` and
  `_response.build_meal_response()`.
- Flutter `Meal.isFavorite` + JSON parse + `copyWith`.

### New widgets

- **`component_collage_hero.dart`** — 1/2/3/4-up layouts with `+N`
  overlay when components > 4. Unavailable overlay chip ("N of M" or
  "All components unavailable"). Optional aspectRatio for use inside
  detail screen's SliverAppBar FlexibleSpaceBar.
- **`component_row.dart`** — one row: thumbnail + name + book subtitle
  + prep/cook chips + trailing chevron. Supports a `trailing` override
  for edit-mode drag handle. Unavailable rows are muted + labeled.

### Detail screen

- `CustomScrollView` + `SliverAppBar` with collage hero.
- Action bar row: Favorite (heart-filled when on, pink; optimistic
  toggle with rollback on error), Plan/Shop/Share (disabled Tooltips
  per Principle 11), Archive (confirmation dialog → archive →
  navigate back), Edit (pushes `/meals/:id/edit`).
- Partial-unavailability banner + all-unavailable banner.
- ComponentRow list; tap row navigates to `/recipes/:recipeId`.

### Edit screen

- AppBar: close leading + **Save** text button (updates name +
  description only).
- Inline name + description TextFields pre-filled from current meal.
- **ReorderableListView** — drag-to-reorder persists per drop via
  `reorderMealComponents`; optimistic with rollback on failure.
- **Add Recipe** FloatingActionButton.extended → opens
  `RecipeMultiselectPicker` with `alreadySelectedIds` =
  current component recipe ids; adds each picked via
  `addRecipeToMeal`.
- **Dismissible** swipe-to-delete per row with ≥2 guard: at 2, swipe
  is rejected with snackbar "A meal needs at least 2 recipes…"; at
  3+, removal commits via `removeRecipeFromMeal`.

### Riverpod invalidation

- `invalidateMeal(ref, mealId, bookId: ...)` now takes `dynamic` so
  both `Ref` (provider-side) and `WidgetRef` (widget-side) can call
  it — the two types share an `invalidate(provider)` signature.
- Detail + edit screens call it after every mutation so
  `mealByIdProvider(id)` re-fetches.

### Tests

- `meal_detail_screen_test.dart` (10 cases) — happy render, action
  bar present, favorite toggle, favorite-error rollback, already-
  favorited → unfavorites, archive flow, archive cancel, partial
  unavailability banner, all-unavailable banner, Plan/Shop/Share
  disabled tooltips.
- `meal_edit_screen_test.dart` (4 cases) — render with pre-fill,
  Save commits via updateMeal, swipe at 3→2 commits, swipe at 2
  rejects.
- `component_collage_hero_test.dart` (8 cases) — 0/2/3/4/6-
  component layouts, `+N` overlay, partial + all-unavailable chips,
  aspectRatio wrapping.
- `meal_model_test.dart` +3 new cases — isFavorite default-false,
  parse true, copyWith override.
- Backend: `test_meal_service.py::TestIsFavorited` (2 cases) +
  `test_meal_router.py::TestGetMeal` +2 (is_favorite true/false)
  and tweaked side_effect lists for every test that now triggers
  an extra MealFavorite lookup.

## Acceptance Criteria

- [ ] Detail screen renders collage hero + action bar + component list.
- [ ] Favorite toggle is wired live with optimistic UI + rollback on
      error.
- [ ] Plan/Shop/Share remain disabled-with-tooltip per Principle 11.
- [ ] Archive flow confirms then navigates back.
- [ ] Edit routes from detail; Cancel/Save semantics match existing
      recipe-edit.
- [ ] Reorder commits via `reorderMealComponents`.
- [ ] Swipe-to-delete at ≥3 removes; at 2 is rejected with a snackbar.
- [ ] Add Recipe FAB opens picker and wires add via `addRecipeToMeal`.
- [ ] Partial-unavailability and all-unavailable states render banners
      + hero chips.
- [ ] `dart analyze lib/features/meals/` clean.
- [ ] Backend: `npx nx run api:test` stays green at 100% coverage.
- [ ] Flutter: `flutter test test/features/meals/` all green.

## File List

New:
- `app/lib/features/meals/widgets/component_collage_hero.dart`
- `app/lib/features/meals/widgets/component_row.dart`
- `app/test/features/meals/component_collage_hero_test.dart`
- `app/test/features/meals/meal_detail_screen_test.dart`
- `app/test/features/meals/meal_edit_screen_test.dart`

Modified:
- `app/lib/features/meals/meal_detail_screen.dart` — full body replacement.
- `app/lib/features/meals/meal_edit_screen.dart` — full body replacement.
- `app/lib/features/meals/models/meal.dart` — `isFavorite` field.
- `app/lib/features/meals/providers/meals_provider.dart` —
  `invalidateMeal` now accepts `dynamic ref`.
- `app/test/features/meals/meal_model_test.dart` — +3 cases.
- `services/api/src/schemas/meal.py` — `MealResponse.is_favorite`.
- `services/api/src/api/v1/meal/_response.py` — call `is_favorited`.
- `libraries/utils/utils/services/meal_service.py` — `is_favorited`
  helper.
- `services/api/tests/test_meal_router.py` — side_effect tweaks + 2
  new is_favorite cases.
- `services/api/tests/test_meal_components.py` — side_effect tweaks.
- `services/api/tests/test_meal_service.py` — `TestIsFavorited`.

## QA Walkthrough

See `mcv-6-qa-walkthrough.md`.
