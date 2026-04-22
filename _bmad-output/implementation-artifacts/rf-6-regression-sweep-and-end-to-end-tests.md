# rf-6 — Regression sweep + end-to-end tests + CI guard

**Status**: done
**Epic**: epic-reactive-foundation-home-imports

## What shipped

Closing story for the epic:
1. End-to-end widget test that drives the full "save a recipe" → "see it on Home without pull-to-refresh" flow through all three layers (rf-1 MutationBus + rf-3 homeContentProvider + rf-4 RecipeService).
2. Code-review checklist committed to `.claude/commands/review.md` so the next epic that touches any mutation path inherits the guardrail.

## Files

- `app/test/features/home/home_end_to_end_reactivity_test.dart` — new. Pumps HomeScreen with one initial recipe; calls `RecipeService.createRecipe('book-1', {'name': 'Fresh Pasta'})` through DI; asserts the new tile appears without a pull-to-refresh gesture, no shimmer flash, and exactly one refetch (getRecipeBookCalls goes 1 → 2).
- `.claude/commands/review.md` — new. 10-item reactive-mutation review checklist + 7-item general review checklist. Used by `/review` and directly referenced by any adversarial review on a mutation-touching PR.

## Coverage summary (epic AC #4)

| Surface | Event(s) | Coverage |
|---|---|---|
| HomeScreen grid | `RecipeCreated`, `RecipeUpdated`, `RecipeArchived`, `RecipeUnarchived`, `RecipeFavorited`, `RecipeForked`, `RecipeMoved`, `RecipeBulkArchived`, `Meal*` | `home_screen_reactivity_test.dart` (rf-3) + `home_end_to_end_reactivity_test.dart` (rf-6) |
| Recipe mutation sites | All recipe events | `recipe_service_test.dart` (rf-4) — 11 tests, one per mutation |
| Imports See-all | `ImportItemDismissed`, `ImportItemRetried`, `ImportJobDismissed` | `import_history_reactivity_test.dart` (rf-5) |
| Activity Read badge | `ImportItemDismissed`, `ImportItemRetried`, `ImportJobDismissed` | `import_history_reactivity_test.dart` (rf-5) |
| Mutation UI copy | All `MutationType` entries | `mutation_failure_copy.dart` map enforces exhaustive coverage |

**Invariants pinned by tests:**
- Event type → list provider invalidation (one emit → one refetch, not two).
- Unrelated event types → zero refetches (opt-in filter).
- Optimistic `setState` paths survive (pfc-4 filter guarantee, dismiss rollback).
- `RecipeBulkArchived` is ONE event, not N per-item.

## QA walkthrough

### Regression (CI-guarded)

- [x] `home_end_to_end_reactivity_test.dart` — new rf-6 test green.
- [x] `home_screen_reactivity_test.dart` — rf-3 tests (2) green.
- [x] `recipe_service_test.dart` — rf-4 tests (11) green.
- [x] `import_history_reactivity_test.dart` — rf-5 tests (6) green.
- [x] `home_filter_no_refetch_test.dart` — pfc-4 zero-network filter guarantee intact.
- [x] `flutter test test/features/home/` — all 83 tests green.
- [x] `flutter test test/features/activity/` — all 130 tests green.
- [x] `flutter test test/features/recipes/` — green.

### Manual dogfood (the epic's single measurable proof)

1. **Paste URL → Save Recipe flow**
   - [ ] Open Home. Tap + → URL Import → paste a link → confirm → wizard → Save Recipe.
   - [ ] Pop back to Home. New tile visible **without** pull-to-refresh, within ~800ms of server 200.

2. **Dismiss failed import flow**
   - [ ] Open Activity Hub → Imports tab with one failed item in the actionable section.
   - [ ] Swipe-dismiss.
   - [ ] Bell badge count decrements within one frame (no 30s wait).
   - [ ] Row gone from the list; See-all footer (if expanded) shows the new archived row at the top.

3. **Failure-path**
   - [ ] Airplane mode → tap heart on a recipe → Snackbar "Couldn't favorite recipe" + Retry.
   - [ ] Offline → swipe-dismiss → Snackbar "Couldn't dismiss, try again" + row restores.

### CI guard (epic AC #5)

- [x] `.claude/commands/review.md` shipped with the reactive-mutation checklist. Any PR touching a mutation path runs through it.
