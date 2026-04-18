# Story mcv-4: Flutter — Meal model / service / provider / router

**Status:** done
**Epic:** epic-meals-create-and-view

## Goal

Ship the Flutter foundation every subsequent mcv-* story leans on:
models, typed service client, Riverpod providers, router wiring, and
screen placeholders so mcv-5's `context.push('/meals/$id')` works
from day one.

## Scope

### Models (`app/lib/features/meals/models/meal.dart`)

- `Meal` — id, name, description, recipeBookId, archivedAt, createdAt,
  updatedAt, components (`List<MealComponent>`), with `isArchived`,
  `componentCount`, `availableComponentCount` getters and a `copyWith`.
- `MealComponent` — recipeId, name, imageUrl, prep/cook time, bookName,
  orderIndex, available, lastKnownName. `displayName` returns
  `lastKnownName` when unavailable.
- `MealSummary` — thin grid-tile shape for list endpoints (up to 4
  `component_image_urls`).

### Service (`app/lib/features/meals/services/meal_service.dart`)

`MealService` wraps `ApiClient` with 12 typed methods:
`listMealsInBook`, `listMeals`, `getMeal`, `createMeal`, `updateMeal`,
`addRecipeToMeal`, `removeRecipeFromMeal`, `reorderMealComponents`,
`archiveMeal`, `restoreMeal`, `favoriteMeal`, `unfavoriteMeal`.

Typed exceptions translate status + `error_code`:
- `MealComponentUnavailableException` (422 / 306) — carries `recipeIds`
  for the Create Meal sheet's per-row Remove affordance.
- `MealComponentDuplicateException` (409 / 303).
- `MealMinComponentsException` (422 / 304).
- `MealReorderMismatchException` (422 / 305).
All other Dio errors bubble up unchanged.

### Providers (`app/lib/features/meals/providers/meals_provider.dart`)

- `mealsByBookProvider(bookId)` — FutureProvider.family for the book
  detail grid.
- `mealsAllProvider` — flat list across every readable book (used by
  the discoverability epic later).
- `mealByIdProvider(id)` — full detail.
- `invalidateMeal(ref, id, {bookId})` — helper that busts the detail +
  (optional) book list + cross-book list.

### Router wiring (`app/lib/core/router/app_router.dart`)

- `/meals/:mealId` → `MealDetailScreen` (full-screen, not nested).
- `/meals/:mealId/edit` → `MealEditScreen`.

Both screens ship in mcv-4 as **placeholders** that resolve
`mealByIdProvider` and render the meal's name + component count. mcv-6
replaces the bodies with the real collage hero, action bar, and
drag-to-reorder edit UX.

### ApiClient additions

12 new `_dio.*` wrapper methods on `ApiClient` covering every Meal
endpoint from mcv-2 and mcv-3.

### DI

`MealService` registered as a `LazySingleton` in
`app/lib/core/di/injection.dart`.

### Tests (`app/test/features/meals/`)

- `meal_model_test.dart` — 8 cases: happy-path Meal.fromJson,
  archived meal + unavailable components, empty components default,
  copyWith overrides (name/description, clearArchivedAt, components),
  MealSummary happy + archived/defaults.
- `meal_service_test.dart` — 15 cases using a `_FakeApi` that extends
  `ApiClient` and stubs every new method: list/get happy paths, every
  write-path happy case, and the four typed-exception mappings (plus
  an "unmapped Dio error bubbles up" case).

## Acceptance Criteria

- [x] Meal + MealComponent + MealSummary parse from JSON round-trip.
- [x] `MealService` covers all 12 endpoints, with typed exceptions
      for the four error codes the UI branches on.
- [x] Providers exist + `invalidateMeal` busts detail + (optional)
      book list + cross-book list.
- [x] Router wired so `/meals/:id` and `/meals/:id/edit` resolve.
- [x] `dart analyze` on every touched file is clean.
- [x] `flutter test test/features/meals/` — 23 cases pass.
- [x] Adjacent tests (`recipe_books/`, `calendar/calendar_screen_test`)
      still pass.

## QA Walkthrough

See `mcv-4-qa-walkthrough.md`.

## File List

New:
- `app/lib/features/meals/models/meal.dart`
- `app/lib/features/meals/services/meal_service.dart`
- `app/lib/features/meals/providers/meals_provider.dart`
- `app/lib/features/meals/meal_detail_screen.dart` (placeholder)
- `app/lib/features/meals/meal_edit_screen.dart` (placeholder)
- `app/test/features/meals/meal_model_test.dart`
- `app/test/features/meals/meal_service_test.dart`

Modified:
- `app/lib/core/services/api_client.dart` — 12 Meal endpoint wrappers.
- `app/lib/core/di/injection.dart` — register MealService.
- `app/lib/core/router/app_router.dart` — `/meals/:id` + `/meals/:id/edit`.
