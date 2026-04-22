# rf-4 — Recipe mutation sites emit MutationBus events

**Status**: done
**Epic**: epic-reactive-foundation-home-imports

## What shipped

New `RecipeService` (Locked Decision #1 — service-layer emits, not UI handlers) wraps every recipe mutation and emits the matching `MutationEvent` **before** returning to the caller. UI handlers now call `RecipeService` and route catch-blocks through `showMutationFailureSnackbar` (Design Principle #6, no silent drops).

## Files

- `app/lib/features/recipes/services/recipe_service.dart` — new. Wraps `ApiClient` for: `createRecipe`, `updateRecipe`, `archiveRecipe`, `restoreRecipe`, `toggleFavorite`, `forkRecipe`, `moveRecipe`, `copyRecipe`, `bulkArchiveRecipes`, `addRecipeNote`, `deleteRecipeNote`. Each emits on the success branch, never on failure.
- `app/lib/core/di/injection.dart` — register `RecipeService` in DI (lazy singleton).
- Call-site migrations (UI handlers → `getIt<RecipeService>()` + `showMutationFailureSnackbar`):
  - `app/lib/features/home/home_screen.dart` — `_toggleFavorite`, `_runRecipeBulkArchive`.
  - `app/lib/features/recipes/recipe_detail_screen.dart` — `_saveVibes`, `_toggleFavorite`, `_archiveRecipe`, `_moveRecipe`, `_copyRecipe`, `_forkRecipe`, `_submitNote`, `_deleteNote`.
  - `app/lib/features/recipes/add_recipe/recipe_wizard_screen.dart` — `_saveRecipe` (create + image-url update).
  - `app/lib/features/recipes/edit_recipe_screen.dart` — `_saveNow`, image-upload post-update.
  - `app/lib/features/recipes/archived_recipes_screen.dart` — `_restoreRecipe`.
  - `app/lib/features/recipe_books/recipe_book_detail_screen.dart` — `_bulkArchive`.
- `app/test/features/recipes/recipe_service_test.dart` — new. 11 unit tests: each mutation emits the right event subtype on success; `archiveRecipe` + `bulkArchiveRecipes` emit nothing on failure; `bulkArchiveRecipes` emits exactly ONE `RecipeBulkArchived` (not N `RecipeArchived`).
- `app/test/features/home/home_bulk_actions_test.dart` — test harness now registers `RecipeService` wrapping the fake ApiClient (bulk-archive path routes through the service).

## Gotchas

- **`RecipeBulkArchived` is a first-class event, NOT N `RecipeArchived`** (Locked Decision #3). If a mixed selection spans multiple books, the service emits once with the first recipe's book id as an anchor — subscribers filter on the event *type*, not the book id (coarse-key rule, Design Principle #1).
- **`toggleFavorite` payload**: post rf-2 the server returns the full `Recipe.Response`; the service reads `is_favorite` from the payload. Pre-rf-2 fallback synthesizes a minimal `{id, is_favorite}` so `RecipeFavorited.recipe` is always a map.
- **Note CRUD emits `RecipeUpdated`**, not a `RecipeNoteAdded` subtype — notes live on the recipe resource, and the coarse-key rule says one event type per list surface. Subscribers that care about notes already subscribe to `RecipeUpdated` via the recipe_provider/home filter.
- **`deleteRecipe` is archive** (soft-delete in the backend). The service's `archiveRecipe(recipeId, bookId:)` wraps it and emits `RecipeArchived`.
- **Failure copy is keyed by `MutationType`** — verbs/nouns live in `mutation_failure_copy.dart`. When a new mutation verb appears, add to the enum + map before calling `showMutationFailureSnackbar`.
- **Test DI**: any test that pumps a screen using `RecipeService` must register the service with the fake ApiClient. Only `home_bulk_actions_test.dart` needed updates in this epic; other tests don't exercise the mutation paths yet.

## QA walkthrough

### Regression (CI-guarded)

- [x] `recipe_service_test.dart` — 11 tests green:
  - createRecipe / updateRecipe / archiveRecipe / restoreRecipe / toggleFavorite / forkRecipe / moveRecipe / bulkArchiveRecipes / addRecipeNote / deleteRecipeNote each emit the right event subtype;
  - archiveRecipe + bulkArchiveRecipes emit nothing on failure;
  - bulkArchiveRecipes emits ONE event, not N.
- [x] `home_bulk_actions_test.dart` — all 7 tests green (bulk-archive path routes through RecipeService unchanged).
- [x] All 706 `flutter test test/features/` tests green.

### Manual dogfood

- [ ] Paste URL → Save Recipe → pop to Home → new tile visible without pull-to-refresh (end-to-end MutationBus happy path).
- [ ] Open a recipe → tap heart → tile's heart flips; back out → Home favorites carousel shows new pin.
- [ ] Long-press 3 recipes → Archive → confirm → all 3 vanish from grid in one frame.
- [ ] Tap heart with airplane mode on → Snackbar: "Couldn't favorite recipe" + Retry.
- [ ] Edit a recipe name → Save → navigate to recipe detail → updated name visible.
- [ ] Fork a recipe into another book → Home grid shows the fork in the target book.
