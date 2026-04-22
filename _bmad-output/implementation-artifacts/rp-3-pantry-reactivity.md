# rp-3 — Pantry stateless refactor + CookingLog handoff

**Status**: done
**Epic**: epic-reactive-migration-books-profile-pantry-and-polish

## What shipped

Closes AC rp-3 #1–#7. `PantryService` is now stateless — the `_current`
cache and `StreamController<Pantry?>` are gone, replaced by Riverpod
providers that own list-state and invalidate on `PantryItem*` events.
The meals/calendar epic's inherited `CookingLogCreated` handoff also
lands here: new `CookingLogService` wraps `POST /v1/cooking-logs` and
`recipeCookingHistoryProvider(recipeId)` subscribes.

## Files

### New

- `app/lib/features/pantry/providers/pantry_provider.dart` —
  `defaultPantryProvider` (the pantry meta), and
  `pantryIngredientsProvider(pantryId)` (family-keyed by pantry id,
  invalidates on `PantryItem*` events scoped to that id).
- `app/lib/features/recipes/services/cooking_log_service.dart` —
  `create(recipeId, feedback) → emits CookingLogCreated`, plus
  `listForRecipe(recipeId)` read.
- `app/lib/features/recipes/providers/cooking_history_provider.dart`
  — `recipeCookingHistoryProvider(recipeId)` subscribes to
  `CookingLogCreated` filtered by recipeId.
- `app/test/features/pantry/pantry_reactivity_test.dart` — 8 tests:
  one emit per mutation, pantry-id filter on provider, unrelated
  event ignored, failed mutation emits nothing, stateless-service
  regression.
- `app/test/features/recipes/cooking_history_reactivity_test.dart`
  — 3 tests: emit on create, family-id filter, unrelated recipe
  ignored.

### Modified

- `app/lib/features/pantry/services/pantry_service.dart` — **breaking
  API change**: `_current`, `_pantryController`, `pantryStream`,
  `current`, `dispose`, `loadDefaultPantry` all removed. Remaining
  surface: `getDefaultPantry`, `addPantryIngredient`,
  `updatePantryIngredient` (NEW — PATCH was on ApiClient only before),
  `deletePantryIngredient`. Each mutation emits on the bus.
- `app/lib/features/pantry/screens/pantry_list_screen.dart` —
  `ConsumerStatefulWidget`. `StreamSubscription<Pantry?>` removed;
  local state collapsed; the screen now watches
  `defaultPantryProvider` and uses `showMutationFailureSnackbar` for
  failure paths. Swipe-to-dismiss undo-Snackbar preserved verbatim
  (success-flow UX, not a failure rollback — Design Principle #4).
- `app/lib/features/pantry/screens/pantry_editor_screen.dart` —
  `ConsumerStatefulWidget`. PATCH now goes through
  `PantryService.updatePantryIngredient`. Reads pantry id from
  `ref.read(defaultPantryProvider).value?.id` when editing.
- `app/lib/core/services/api_client.dart` — added `createCookingLog`
  (POST) and `getRecipeCookingLogs` (query scoped by recipe_id).
- `app/lib/core/di/injection.dart` — registered `CookingLogService`.
  `PantryService` registration keeps working since the constructor
  is backward-compatible (optional `api` param).

### Deferred

- `PostCookFeedbackSheet` currently only writes to local
  `RecipeCacheService.logCook` and adds a recipe note — it does
  NOT hit `/v1/cooking-logs`. The backend endpoint exists and the
  service + provider are ready; the widget integration is a
  future polish epic. Documented as follow-on.

## QA walkthrough

### Regression (CI-guarded)

- [x] `pantry_reactivity_test.dart` — 8 tests green (emits,
  provider invalidation scoping, stateless regression).
- [x] `cooking_history_reactivity_test.dart` — 3 tests green.
- [x] `pantry_editor_screen_test.dart` — existing 4 tests still
  green (migrated harness to `ProviderScope`).

### Manual dogfood (dogfood-proof step 3)

1. Pantry → + → add "Flour".
   - [ ] Row appears within one frame of server 200 (no skeleton
     flash; `valueOrNull`-during-refetch guard).
2. Swipe-delete the "Flour" row.
   - [ ] Row disappears immediately.
   - [ ] Undo Snackbar visible; tap Undo → row returns.
3. Induce one failure (airplane mode + add).
   - [ ] Central Snackbar: "Couldn't add pantry item" + Retry.

### Gotcha

- The epic text assumed `PostCookFeedbackSheet` calls a cooking-log
  POST today; it does not. The endpoint exists, the service + provider
  are wired, but the UI handoff is deferred. Future PM dogfood step
  #5 ("Recipe detail → Mark Cooked → cooking-history updates")
  requires that future epic to land first.
