# Story mcv-5: Flutter — Create Meal (multi-select entry + standalone)

**Status:** ready-for-dev
**Epic:** epic-meals-create-and-view

## Goal

Wire the two Create-Meal entry paths in `recipe_book_detail_screen.dart`:
the **multi-select action bar** leading action (the fast path Leo uses
on Day 1) and the **"+ New Meal" overflow** item (the standalone path
when he hasn't already multi-selected). Both surface the same modal —
`CreateMealSheet` — which handles naming + component review + POST.

The standalone path also ships a reusable `RecipeMultiselectPicker`
modal that searches across every book the user can read, defaulting
to the current book's recipes.

## Scope

### New files

- **`app/lib/features/meals/widgets/create_meal_sheet.dart`**
  - `CreateMealSheet` — modal bottom sheet. Shared for both entry
    modes. Props: `bookId`, `bookName`, `initialComponents`
    (nullable; multi-select pre-fills, standalone starts empty),
    `onCreated` callback (fires with the new Meal for cache
    invalidation + navigation).
  - Body: Name field (autofocus; pre-filled with first two component
    names joined by `" + "`, truncated to 60 chars + `…`),
    Description, horizontal scrollable **component preview strip**
    (long-press thumbnail → remove from draft with Undo snackbar),
    and an **Add recipes** button that opens
    `RecipeMultiselectPicker` (always visible; standalone auto-opens
    the picker after the first frame).
  - Create button disabled when
    `name.trim().isEmpty || components.length < 2`, with a helper
    subtitle "A meal needs at least 2 recipes" at <2.
  - On `422 MEAL_COMPONENT_UNAVAILABLE` (code 306): inline
    `ErrorBanner` "Some recipes are no longer available"; the
    offending rows in the preview strip gain a Remove affordance
    label; Create stays disabled until the draft has ≥2 available
    components.

- **`app/lib/features/meals/widgets/recipe_multiselect_picker.dart`**
  - `RecipeMultiselectPicker` — modal bottom sheet, full-height.
    Props: `bookId` (default source book), `alreadySelectedIds`
    (visually disabled + "Added" badge in edit-mode reuse later).
  - Defaults to `ApiClient.getRecipes(bookId)` on open; as soon as
    the user types, switches to `ApiClient.search(query, scope:
    'recipes', limit: 50)` and shows cross-book results.
  - Returns `List<PickedRecipe>` on Done.

### Modified files

- **`app/lib/features/recipe_books/recipe_book_detail_screen.dart`**
  - Bulk action bar gains a **leading** `_BulkActionButton` for
    Create Meal (icon `Icons.set_meal_outlined`), enabled at
    `_selectedRecipeIds.length >= 2 && !_isBulkOperating`.
  - Header overflow `PopupMenuButton` gains a **New Meal**
    `PopupMenuItem` immediately below the existing import items
    (only when `_userRole != 'viewer'`).
  - Both open `CreateMealSheet`. Multi-select maps selected recipe
    ids → `DraftMealComponent` using the already-loaded `_recipes`
    list (no extra fetch). Standalone passes empty initial
    components.
  - On success: `ScaffoldMessenger` green snackbar "Meal created",
    navigate to `/meals/$id`, reload the book (so the grid will
    pick up the new Meal when mcv-7 ships).

### Tests (`app/test/features/meals/`)

- `create_meal_sheet_test.dart` — ≥8 cases:
  1. Renders with two initial components → Create enabled when
     name is non-empty.
  2. Disables Create when draft drops below 2 (long-press one
     component → remove → banner reads "A meal needs at least 2
     recipes" + Create disabled).
  3. Happy-path submit: fills name, taps Create, verifies POST
     payload matches `{name, description?, component_recipe_ids:
     [a, b]}` and `onCreated` fires with the returned Meal.
  4. Cancel dismisses without submit.
  5. Name pre-fill joins first two component names via `" + "`
     and truncates at 60 chars + `…`.
  6. 422 COMPONENT_UNAVAILABLE response (code 306) renders the
     inline error banner; Create stays disabled; removing
     flagged components re-enables Create.
  7. Description is optional — creating with empty description
     omits the field from the payload.
  8. Standalone mode (no initialComponents) auto-opens the picker
     on first frame (use `find.byType(RecipeMultiselectPicker)`).

- `recipe_multiselect_picker_test.dart` — ≥5 cases:
  1. Renders book-scoped list on open (stubs `getRecipes`).
  2. Typing switches to global search (stubs `search`).
  3. Tap row toggles selection (checkbox state).
  4. Done returns selected `PickedRecipe` list.
  5. Recipes in `alreadySelectedIds` render an "Added" badge and
     are not tappable.

### Stub-path discipline

- MealService is replaced via `GetIt` in test setup (same pattern
  as `plan_meal_sheet_test.dart`). Register a `_FakeMealService`
  that extends `MealService` with a null-safe ApiClient dummy, and
  stub only the methods the tests reach. Same for ApiClient in the
  picker test.

## Acceptance Criteria

- [ ] `recipe_book_detail_screen.dart` bulk bar gains **Create
      Meal** as the leading action; enabled at ≥2, disabled at <2.
- [ ] Header overflow gains **New Meal** item; visible only when
      `_userRole != 'viewer'`.
- [ ] Both entry paths open `CreateMealSheet`. Multi-select
      pre-fills the draft from selected recipes; standalone opens
      the picker first.
- [ ] Create button disabled until
      `name.trim().isNotEmpty && components.length >= 2`.
- [ ] On `422` with code `306` the inline error banner renders
      and per-row Remove affordance appears on flagged rows.
- [ ] On success: sheet dismisses, green snackbar, route to
      `/meals/$id`, book reloads.
- [ ] `dart analyze` on every touched file is clean.
- [ ] `flutter test test/features/meals/` — new suites pass plus
      the 23 existing mcv-4 tests stay green.

## File List

New:
- `app/lib/features/meals/widgets/create_meal_sheet.dart`
- `app/lib/features/meals/widgets/recipe_multiselect_picker.dart`
- `app/test/features/meals/create_meal_sheet_test.dart`
- `app/test/features/meals/recipe_multiselect_picker_test.dart`

Modified:
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart`

## QA Walkthrough

See `mcv-5-qa-walkthrough.md`.
