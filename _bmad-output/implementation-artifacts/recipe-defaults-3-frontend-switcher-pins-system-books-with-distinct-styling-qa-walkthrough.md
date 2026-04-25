# recipe-defaults-3 — QA Walkthrough

**Story:** `recipe-defaults-3-frontend-switcher-pins-system-books-with-distinct-styling`
**Date:** 2026-04-25

## Summary

Adds a "System" section pinned at the top of `RecipeBooksScreen` with
two tiles — ❤️ Favorites (routes to `/favorites`) and 📒 Trying Out
(routes to the system book's detail). The Trying Out row from the API
is filtered out of the user-books list so it isn't rendered twice. The
recipe-book detail screen hides Edit + Archive popup-menu items when
`is_system=true` so the UI matches the backend guards from story 1.

A small `/favorites` route renders the user's favorited recipes via
the existing `getFavorites()` API. Tapping a row navigates to recipe
detail.

## Files

| File | Status | Purpose |
|---|---|---|
| `app/lib/features/recipes/favorites_screen.dart` | new | `/favorites` destination |
| `app/lib/features/recipe_books/recipe_books_screen.dart` | modified | System section + filtered user list |
| `app/lib/features/recipe_books/recipe_book_detail_screen.dart` | modified | Hide Edit/Archive on system books |
| `app/lib/core/router/app_router.dart` | modified | `/favorites` route |
| `app/test/recipe_books_test.dart` | modified | 3 new widget tests for the System section |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | modified | flip `recipe-defaults-3-...: backlog → done` |
| `_bmad-output/implementation-artifacts/recipe-defaults-3-...md` | new | Story spec |
| `_bmad-output/implementation-artifacts/recipe-defaults-3-...-qa-walkthrough.md` | new | This file |

## Acceptance-criteria mapping

| AC | Verified by | Where |
|---|---|---|
| AC #1 System section header | `renders System header + both pinned tiles` | `recipe_books_test.dart` |
| AC #2 Favorites tile | same test + key `'system-tile-favorites'` | `recipe_books_test.dart` |
| AC #3 Trying Out tile | same test + key `'system-tile-trying-out'` + `7 recipes` count | `recipe_books_test.dart` |
| AC #4 Divider | `Divider` widget at index 3 in the harness | `recipe_books_test.dart` |
| AC #5 System book NOT duplicated | `Trying Out is NOT duplicated in the user-books list` | `recipe_books_test.dart` |
| AC #6 Detail-screen guard | `if (_recipeBook?['is_system'] != true)` wraps both Edit and Archive popup items | `recipe_book_detail_screen.dart` |
| AC #7 Favorites screen | `/favorites` route + screen renders list using existing `getFavorites()` | `favorites_screen.dart`, `app_router.dart` |
| AC #8 Widget tests | 3 new tests in `RecipeBooksScreen System section` group; all pass | `recipe_books_test.dart` |
| AC #9 Analyzer + tests | `dart analyze` introduces zero new warnings; existing recipe_books tests + new System-section tests all green (8/8 in `test/recipe_books_test.dart` + 46/46 in `test/features/recipe_books/`) | local |

## Test inventory (3 new widget tests, all passing)

| # | Test | What it proves |
|---|---|---|
| W1 | `renders System header + both pinned tiles when system book present` | Header text "System" rendered; both tile keys present; "Trying Out" tile shows recipe count from API row (`7 recipes`); user book renders below the divider. |
| W2 | `Trying Out is NOT duplicated in the user-books list` | Among two API rows (one system, one user), "Trying Out" appears exactly once; user-books list excludes the system row. |
| W3 | `System section renders Favorites tile even with no Trying Out book` | Edge case: when the back-fill hasn't run yet for a user, Favorites still pins; Trying Out tile collapses to `SizedBox.shrink()`; user books still render. |

## Adversarial review notes

1. **`firstWhere` returning `null`.** `_recipeBooks` is `List<dynamic>`,
   so `firstWhere(... orElse: () => null)` is type-safe (dynamic
   accepts null). The W3 test exercises this path. ✓
2. **System tile in detail page also has `is_system` accessible.**
   Story 1's `GET /v1/recipe-books/{id}` response now includes
   `is_system`; `_recipeBook?['is_system']` resolves correctly. ✓
3. **Pre-existing analyzer warnings unchanged.** Three pre-existing
   warnings in `recipe_book_detail_screen.dart` and one in
   `recipe_books_screen.dart` were present before this story — none
   were introduced by these changes. New file
   `favorites_screen.dart` analyzes clean.
4. **`/favorites` route order.** Placed inside the same group as
   `/recipes/archived` (top-level routes that must avoid `/recipes/:id`
   collisions, even though `/favorites` doesn't collide with anything;
   keeping it adjacent to similar list-routes for readability).
5. **No side-effects on the existing user-books long-press menu.**
   The user-books "Set as default" path still works for user books;
   system tiles use the new `_SystemBookTile` widget that does not
   wire `onLongPress`, so the system-book locking AC is satisfied
   (no rename / no delete affordance — the existing menu was already
   limited to "set as default" for user books).

## Manual QA (runtime sanity)

Not run on a real device — out of band for /dev. Smoke checklist for
the next manual session:

- [ ] Open the Recipe Books screen with a fresh test account; verify
      the System section renders with both tiles + divider above the
      "My Recipes" / user-created books.
- [ ] Tap "Favorites" → arrives on `/favorites` listing.
- [ ] Tap "Trying Out" → arrives on `/recipe-books/{trying_out_id}`
      detail page.
- [ ] Open the Trying Out detail page popup-menu → confirm "Edit" and
      "Archive" entries are absent; "Import URL", etc. still render.

## Done

- [x] System section + tiles render in `RecipeBooksScreen`.
- [x] User-books list filters `is_system=true` out.
- [x] Detail-screen popup hides Edit + Archive on system books.
- [x] `/favorites` route + screen shipped.
- [x] 3 new widget tests pass; 5 pre-existing recipe-book widget tests still green; 46 feature tests still green.
- [x] `dart analyze` introduces zero new warnings.
- [x] Sprint-status flipped `recipe-defaults-3-...: backlog → done`.
- [x] Atomic commit — only story-scoped files staged.
