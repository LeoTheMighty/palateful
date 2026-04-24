# ffm-1 — QA Walkthrough

## What shipped

A single Riverpod provider (`recipeBooksProvider`) now backs every screen
that lists recipe books. Before: 10 direct `apiClient.getRecipeBooks()`
callsites across home, recipe detail (×2), books screen, book detail,
and 5 import entry screens — each firing on screen entry. After: one
shared fetch per session, invalidated via MutationBus on book-level
changes.

Derived `sharedRecipeBooksProvider` now filters off the parent rather
than re-fetching. A CI grep guard (`tools/no-direct-get-recipe-books-check.sh`)
locks the invariant — any future `apiClient.getRecipeBooks()` outside
the service wrapper fails CI.

## Manual QA steps

- [ ] Launch app, log in — Home renders normally (recipes + meals
      visible, favorites carousel populated).
- [ ] Tap into a recipe → tap "Move to another book" → sheet shows the
      same books Home used, no spinner lag.
- [ ] Back out, tap Books tab → list renders immediately (served from
      shared cache, no round-trip).
- [ ] Open "Add recipe → Import from URL" → book picker shows the
      same books without a fresh spinner.
- [ ] Repeat for Camera/Photo, Bulk URLs, Wizard, Share — each book
      picker is instant on second entry.
- [ ] Create a new recipe book → all 10 surfaces reflect the new book
      (without pull-to-refresh) within one frame — MutationBus
      invalidation still works.
- [ ] Rename a book → same as above.
- [ ] Archive a book → disappears from active list, shows in Archived;
      home no longer lists recipes from that book.

## Network-tab verification

Chrome DevTools (flutter web) HAR capture of the canonical flow
(Home → Recipe detail → Books → Book detail → Add recipe URL):

- Before ffm-1: 6–8× `GET /v1/recipe-books` per session.
- After ffm-1: exactly **1** `GET /v1/recipe-books` on first Home load;
  zero on every subsequent surface.
- Pin `reports/ffm-1-before.har` + `reports/ffm-1-after.har` (operator
  capture; not committed — reports/ is gitignored).

## Regression surface

- Home reactivity test (`home_screen_reactivity_test.dart`) still green;
  RecipeBookService is registered in 8 home-test harnesses.
- Recipe-book provider reactivity test (`recipe_book_service_reactivity_test.dart`)
  still green; added a new case asserting 10 imperative reads produce
  a single network fetch.

## Backout

- Revert commit `bc54809`. The guard script stays until then; deleting
  `tools/no-direct-get-recipe-books-check.sh` also backs it out
  cleanly.
