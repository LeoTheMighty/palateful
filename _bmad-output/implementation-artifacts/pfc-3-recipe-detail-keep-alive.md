# Story pfc-3 — Recipe detail cached via keep-alive family provider

**Status:** review
**Epic:** epic-perf-flutter-client-polish
**Generated:** 2026-04-21

## Summary

Reopening the same recipe within ~5 minutes is now zero-network. The
detail screen fetches through a new `recipeProvider` (family-keyed,
autoDispose + `ref.keepAlive()` + 5-min TTL). Every mutation site —
inside the detail screen and across the other recipe-mutating screens
— fires `invalidateRecipe(ref, recipeId)` so cached data is dropped
after writes.

`recipe_detail_screen.dart` migrates from `StatefulWidget` →
`ConsumerStatefulWidget`. The heavy local-state surface (notes,
favorite toggle, servings scaler, etc.) is preserved — only the
initial load and mutation-invalidation paths wire through Riverpod.

## Mutation-site enumeration (pre-implementation)

Grepped `updateRecipe|archiveRecipe|deleteRecipe|toggleFavorite|_saveVibes|_toggleFavorite|moveRecipe|addRecipeNote|deleteRecipeNote|restoreRecipe|restoreRecipeVersion|bulkArchiveRecipes|bulkMoveRecipes` across `app/lib/features/**`:

- Inside `recipe_detail_screen.dart`:
  - `_saveVibes` at line 109 — updateRecipe(primary_vibe, secondary_vibe).
  - `_toggleFavorite` at line 134 — toggleFavorite.
  - `_archiveRecipe` at line 280 — deleteRecipe (archive).
  - `_moveRecipe` at line 382 — moveRecipe (changes recipe_book_id).
  - `_copyRecipe` / `_forkRecipe` — create a NEW recipe; source
    unchanged → no invalidation (cache for source stays valid).
  - `_submitNote` at line 1196 — addRecipeNote.
  - `_deleteNote` at line 1220 — deleteRecipeNote.
- External sites (must invalidate):
  - `edit_recipe_screen.dart:239` — full metadata save.
  - `edit_recipe_screen.dart:395` — image_url patch after upload.
  - `recipe_version_diff_screen.dart:370` — restoreRecipeVersion.
  - `archived_recipes_screen.dart:132` — restoreRecipe.
  - `cook_mode_screen.dart:129` — addRecipeNote (pending-note flush).
  - `cook_mode/widgets/post_cook_feedback_sheet.dart:61` — post-cook
    addRecipeNote online path.
  - `home_screen.dart:326` — toggleFavorite (home grid tap).
  - `home_screen.dart:875` — bulkArchiveRecipes (home bulk archive).
  - `recipe_book_detail_screen.dart:485` — bulkMoveRecipes.
  - `recipe_book_detail_screen.dart:533` — bulkArchiveRecipes.
- Intentionally skipped:
  - `add_recipe/recipe_wizard_screen.dart:188` — updates the
    just-created recipe's image_url. No pre-existing cache entry
    exists for a brand-new id; invalidation is a no-op.

## Scope of change

- New `app/lib/features/recipes/providers/recipe_provider.dart`:
  - `recipeProvider = FutureProvider.family.autoDispose<Map<String,
    dynamic>, String>`.
  - `ref.keepAlive()` paired with a 5-minute `Timer` that closes the
    link on expiry (TTL). `ref.onDispose` cancels the timer.
  - `invalidateRecipe(refOrContext, recipeId)` helper accepts a
    `Ref`, `WidgetRef`, `ProviderContainer`, or `BuildContext` so both
    Consumer and non-Consumer widgets can invalidate uniformly.
- `recipe_detail_screen.dart`: `StatefulWidget` →
  `ConsumerStatefulWidget`. `_loadRecipe` reads
  `ref.read(recipeProvider(id).future)` instead of calling
  `apiClient.getRecipe` directly. Mutation paths (`_saveVibes`,
  `_toggleFavorite`, `_archiveRecipe`, `_moveRecipe`, `_submitNote`,
  `_deleteNote`) add one `invalidateRecipe(ref, widget.recipeId)` call
  each, post-success. Unused `_authService` field removed.
- External mutation sites get one `invalidateRecipe(...)` call each,
  post-success.
- New widget test `recipe_detail_cache_test.dart`:
  - Test 1: open → back → reopen within TTL → `getRecipe` calls == 1.
  - Test 2: open → mutate via `updateRecipe` + `invalidateRecipe` →
    back → reopen → `getRecipe` calls == 2; new payload visible.
  - Test 3: open → back → advance fake clock 6 min → reopen →
    `getRecipe` calls == 2 (TTL dropped the cache).

## File List

- app/lib/features/recipes/providers/recipe_provider.dart  [NEW]
- app/lib/features/recipes/recipe_detail_screen.dart  [MODIFIED]
- app/lib/features/recipes/edit_recipe_screen.dart  [MODIFIED]
- app/lib/features/recipes/recipe_version_diff_screen.dart  [MODIFIED]
- app/lib/features/recipes/archived_recipes_screen.dart  [MODIFIED]
- app/lib/features/recipes/cook_mode/cook_mode_screen.dart  [MODIFIED]
- app/lib/features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart  [MODIFIED]
- app/lib/features/home/home_screen.dart  [MODIFIED]
- app/lib/features/recipe_books/recipe_book_detail_screen.dart  [MODIFIED]
- app/test/features/recipes/recipe_detail_cache_test.dart  [NEW]

## Acceptance criteria

- [x] Pre-implementation enumeration of every mutation site captured
  above in "Mutation-site enumeration". No grep-after-the-fact.
- [x] `recipe_detail_screen.dart` is a `ConsumerStatefulWidget`.
- [x] `recipeProvider` is family-keyed + autoDispose + keepAlive +
  5-min TTL. (Epic spec'd `AsyncNotifierProvider.family.autoDispose`;
  used `FutureProvider.family.autoDispose` for the same behavior with
  less ceremony — matches the existing `mealByIdProvider` pattern.)
- [x] Every enumerated mutation site fires `invalidateRecipe(...)`
  post-success.
- [x] Widget tests 1 / 2 / 3 pass. Exactly 3 widget tests — no more.
- [x] All 205 tests in `test/features/{recipes,home,activity}` pass —
  zero regression against existing coverage.

## Code review findings (addressed)

- [HIGH] **Invalidator accepts BuildContext** — some mutation sites
  (`edit_recipe_screen`, `archived_recipes_screen`,
  `recipe_version_diff_screen`, `cook_mode_screen`,
  `post_cook_feedback_sheet`, `recipe_book_detail_screen`) are plain
  `StatefulWidget` and don't hold a `WidgetRef`. Made
  `invalidateRecipe` accept `BuildContext` via
  `ProviderScope.containerOf` so the same one-liner works everywhere,
  without forcing a full ConsumerStatefulWidget migration on every
  file. Alternative would have been to migrate 6 more files —
  rejected as scope creep and a test-coverage tax.
- [MEDIUM] **TTL timer leak on screen teardown** — if the 5-min
  Timer were created naively outside the provider build, it would
  leak past container dispose. Fixed by scoping both
  `ref.keepAlive()` and the `Timer` via `ref.onDispose` inside
  `build`. Widget tests explicitly dispose the `ProviderContainer` at
  test end (the binding's `_verifyInvariants` check runs before
  `addTearDown` callbacks, so inline disposal is the correct hygiene).
- [MEDIUM] **Copy/fork don't mutate source** — reviewed each of
  `_copyRecipe`, `_forkRecipe`, and `recipe_wizard_screen.dart`'s
  image_url update; none need to invalidate the source (copy/fork
  creates a new recipe id with no cached entry; wizard's
  just-created recipe has no prior cache). Skipping is the right
  call.
- [LOW] **Invalidator no-op for non-cached ids** — if a caller
  invalidates a recipe id that was never cached, Riverpod's
  `invalidate` is a no-op. Safe to call speculatively.
- [LOW] **`pumpAndSettle` + CircularProgressIndicator pitfall** —
  the detail screen's loading shimmer used to never settle in tests.
  The provider-driven load resolves in one async pump; widget tests
  use `pumpAndSettle` successfully post-migration.

## QA walkthrough

See `pfc-3-qa-walkthrough.md`.

## Gotchas for next stories

- `invalidateRecipe` lives at `app/lib/features/recipes/providers/
  recipe_provider.dart`. Any new recipe-mutating callsite MUST call
  it — otherwise cached detail data goes stale silently.
- TTL is 5 minutes. If a user edits on Device A while Device B is
  viewing the cached detail, Device B sees stale data until next
  invalidation (tab switch / pull-to-refresh / TTL expiry). This is
  consistent with the rest of the app's per-device cache model.
- `invalidateRecipe` uses `ProviderScope.containerOf(context)` for
  the BuildContext path. If a future story introduces nested
  ProviderScopes, callers must ensure they pass the correct one.
  Today we have a single top-level ProviderScope, so it's safe.
