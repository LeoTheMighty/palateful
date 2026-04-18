# QA Walkthrough: mcv-4

Flutter foundation story — no user-facing flow yet. Placeholder screens
ship so mcv-5's create-success navigation works end-to-end.

## Manual smoke

1. **Run the app** (`cd app && flutter run`) with an authed user + an
   existing Meal id (create one via the mcv-2 API with `curl`).
2. **Direct-navigate** to `/meals/<id>` — confirms the route resolves,
   `mealByIdProvider` fetches, and the placeholder renders the name +
   `{N} recipes`.
3. **Navigate** to `/meals/<id>/edit` — placeholder renders with the
   name.
4. **Provider invalidation.** From a helper `debugPrint`, call
   `invalidateMeal(ref, id, bookId: bookId)` after a mutation and
   confirm the placeholder re-fetches.

## Automated

- `dart analyze lib/features/meals/` → clean.
- `flutter test test/features/meals/` → 23 tests pass.
- Spot-check adjacent regression — `flutter test test/features/calendar/
  calendar_screen_test.dart` + `test/features/recipe_books/` stay green.

## Out of scope (lands later)

- Collage hero + action bar + drag-to-reorder → mcv-6.
- Create Meal sheet + "+ New Meal" entry → mcv-5.
- Meal tile in the book grid → mcv-7.
