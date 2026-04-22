# rp-1 — RecipeBookService + providers + screens

**Status**: done
**Epic**: epic-reactive-migration-books-profile-pantry-and-polish

## What shipped

Closes AC rp-1 #1–#10. Recipe-book mutations now emit on the MutationBus
from a dedicated service; the Books surface consumes providers that
subscribe to those events and invalidate. Failure paths route through
the central `showMutationFailureSnackbar`. The WS adapter
(`RecipeBookSyncService`) additionally lowers inbound `recipe_added` /
`recipe_updated` / `recipe_removed` frames into the bus, so reactive
subscribers react uniformly to "my mutation" and "partner broadcast".

## Files

### New

- `app/lib/features/recipe_books/services/recipe_book_service.dart` —
  new service. Methods: `listRecipeBooks`, `listArchivedRecipeBooks`,
  `getRecipeBook`, `createRecipeBook`, `updateRecipeBook`,
  `archiveRecipeBook`, `restoreRecipeBook`, `deleteRecipeBook`,
  `addMember`, `updateMemberRole`, `removeMember`, `bulkMoveRecipes`,
  `bulkArchiveRecipes`, `bulkUpdateTags`. Stateless — no cached lists,
  no StreamControllers.
- `app/lib/features/recipe_books/providers/recipe_books_provider.dart`
  — `recipeBooksProvider`, `archivedRecipeBooksProvider`,
  `activeRecipeBookProvider(bookId)`, `sharedRecipeBooksProvider`,
  `recipeBookMembersProvider(bookId)`. Each subscribes to the bus
  with a typed filter and invalidates on relevant events.
- `app/test/features/recipe_books/recipe_book_service_reactivity_test.dart`
  — 21 tests: one per mutation emit, plus provider invalidation
  scoping (type filter, book-id filter), plus a failed-mutation
  emits-nothing regression, plus the stateless-service regression.
- `app/test/features/recipe_books/rename_recipe_book_propagates_test.dart`
  — AC #6. Drives `updateRecipeBook('b1', ...)`; asserts both
  `recipeBooksProvider` and `activeRecipeBookProvider('b1')` refetch
  and render the new name within one frame.

### Modified

- `app/lib/core/state/mutation_event.dart` — extended the recipe-book
  stubs: `RecipeBookArchived` gets `restoredDefaultBookId`; new
  subtypes `RecipeBookUnarchived`, `RecipeBookDeleted`,
  `RecipeBookMemberAdded`, `RecipeBookMemberChanged`. Added a new
  `recipeBookMember` category.
- `app/lib/core/state/mutation_failure_copy.dart` — added copy for
  every rp-1 `MutationType` (createRecipeBook, updateRecipeBook,
  archiveRecipeBook, restoreRecipeBook, deleteRecipeBook,
  addBookMember, updateBookMemberRole, removeBookMember, bulk*).
- `app/lib/core/state/mutation_snackbar.dart` — added optional
  `rollback:` param (rp-2 notification-prefs relies on it).
- `app/lib/core/di/injection.dart` — registered `RecipeBookService`.
- `app/lib/features/recipe_books/services/recipe_book_sync_service.dart`
  — WS `_handleMessage` cases emit `RecipeCreated/Updated/Archived`
  alongside existing StreamControllers (additive, not replacing).
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` —
  archive / rename / bulk-move / bulk-tags mutations now go through
  `RecipeBookService`; failure paths routed to
  `showMutationFailureSnackbar`.
- `app/lib/features/recipe_books/recipe_books_screen.dart` — create
  now routes through the service.
- `app/lib/features/recipe_books/archived_recipe_books_screen.dart`
  — restore routes through the service.
- `app/lib/features/recipe_books/recipe_book_members_screen.dart` —
  add / update-role / remove all go through the service.

## QA walkthrough

### Regression (CI-guarded)

- [x] `recipe_book_service_reactivity_test.dart` — 21 tests green
  (one per mutation + provider scoping + stateless guarantee).
- [x] `rename_recipe_book_propagates_test.dart` — rename propagates
  to two subscribers in one frame.
- [x] `recipe_book_sync_service_test.dart` — existing tests still
  green (WS adapter emits are additive).
- [x] `recipe_book_detail_realtime_test.dart` — live-dot UX
  unchanged.
- [x] `flutter test test/features/recipe_books/` — 45 tests pass.
- [x] `flutter test test/features/home/` + `test/features/activity/`
  — no regressions; `PantryItemCreated` compat alias keeps the
  foundation reactivity test green.

### Manual dogfood (dogfood-proof steps 1+6)

1. Open a recipe book → Rename → "Weeknight Wins".
   - [ ] Books list shows new name without pull-to-refresh.
   - [ ] Home header (active book) shows new name.
   - [ ] Shared-books section (if applicable) shows new name.
2. Induce one failure (archive a book with airplane mode on).
   - [ ] Snackbar: `"Couldn't archive recipe book"` + Retry.
   - [ ] Tap Retry → toggle airplane off → reconciles.

### Follow-ups (not blocking)

- Full ConsumerWidget rewrite of `recipe_book_detail_screen.dart` is
  deferred — the service + providers are in place, but the existing
  imperative `_loadRecipeBook()` pattern remains on the detail
  screen. Provider-first consumers (future surfaces) work today; the
  rewrite is a UI-layer polish pass.
- `RecipeBookSyncService._handleMessage` still has an untyped
  `catch (e)` at the bottom for malformed-message recovery — rp-5
  will allowlist this entry.
