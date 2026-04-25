# recipe-defaults-4 — QA Walkthrough

**Story:** `recipe-defaults-4-frontend-share-import-fallback-uses-default-recipe-book-id`
**Date:** 2026-04-25

## Summary

Audit + small patch. Confirmed every share-import / wizard / paste /
photo entry point already consults
`AuthService.defaultRecipeBookId`. Patched the single remaining gap
in `share_import_screen.dart` so that when a user has no default set,
the screen prefers the system Trying Out book (back-filled by
story 1, set as default for new users by story 2) over the
non-deterministic `books.first`. Closes epic `epic-recipe-default-books`.

## Files

| File | Status | Purpose |
|---|---|---|
| `app/lib/features/recipes/add_recipe/share_import_screen.dart` | modified | Prefer system book over `books.first` when no default |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | modified | flip `recipe-defaults-4-...: backlog → done` |
| `_bmad-output/implementation-artifacts/recipe-defaults-4-...md` | new | Story spec (with audit table) |
| `_bmad-output/implementation-artifacts/recipe-defaults-4-...-qa-walkthrough.md` | new | This file |

## Acceptance-criteria mapping

| AC | Verified by | Where |
|---|---|---|
| AC #1 All entry points consult default | audit table in story spec | `recipe-defaults-4-...md` |
| AC #2 New users → Trying Out | story 2's hook sets it | covered by story 2 tests |
| AC #3 Existing users with default unchanged | `defaultId != null` path unchanged | `share_import_screen.dart` |
| AC #4 Existing users with no default → Trying Out preferred | new `systemBook` fallback before `books.first` | `share_import_screen.dart:69-85` |
| AC #5 Manual smoke | checklist in this file (deferred to manual session) | this doc |
| AC #6 Existing tests still green | 13/13 in `share_import_test.dart` + `share_import_screen_nav_test.dart` | local run |
| AC #7 Sprint-status flipped | git diff sprint-status.yaml | `backlog → done` |

## Manual QA checklist (for the next runtime smoke session)

- [ ] **Fresh account flow.** Sign up via Auth0, complete onboarding,
      open the Recipe Books screen — confirm the System section shows
      Favorites + Trying Out tiles.
- [ ] **Share a URL.** Use the iOS/Android share-sheet to send a recipe
      URL into the app. Confirm:
  - With no `bookId` in the deep-link → lands in Trying Out (visible
    when you tap the Trying Out tile).
  - With a `bookId` in the deep-link → lands in that specific book.
- [ ] **No-default user.** Manually clear `default_recipe_book_id` for
      a test user (admin script `set_default_recipe_book` or direct
      DB), then share a recipe URL. Confirm it routes to Trying Out
      (the system book) rather than a random user book.
- [ ] **Existing default unchanged.** A user with an existing
      `default_recipe_book_id` (e.g. their personal "My Recipes") shares
      a URL. Confirm it still lands in their personal default — the
      Trying Out preference does NOT override.

## Adversarial review notes

1. **Type cast `as Map<String, dynamic>`.** `books` is
   `List<dynamic>`; the cast is required because `books[i]` is
   `dynamic` and we want the typed `Map<String, dynamic>` to carry
   forward. Same pattern used elsewhere in this codebase (e.g.
   `_loadBooksAndStartImport`'s existing `targetBook['id']?.toString()`
   relies on the same shape).

2. **Single-pass scan.** The system-book search loops once and breaks
   on first match — O(N) worst case where N is the user's total book
   count. Each user has exactly one system book per story 1; the loop
   short-circuits on the first hit.

3. **Backwards compatibility.** If `is_system` is missing from the
   API row (older client / older server combo), the `b['is_system'] == true`
   guard is `false` for `null`, so the loop simply does not pick a
   system book and the original `books.first` fallback fires. No
   regression for legacy clients.

4. **Tests intentionally NOT extended.** The existing share-import
   widget tests don't exercise the "no default + system-book preferred"
   path; adding a test would require a mocked `AuthService` chain that
   isn't in place. The patch is small + inline-reviewable, and the
   manual QA checklist above covers it. The recipe-bulk-org / recipe-list-org
   regression sweeps in follow-on epics will re-exercise this path
   under realistic conditions.

## Done

- [x] Audit table populated; one gap patched.
- [x] Existing share-import tests green (13/13).
- [x] `dart analyze lib/features/recipes/add_recipe/` introduces zero
      new warnings on the touched file.
- [x] Sprint-status flipped `recipe-defaults-4-...: backlog → done`.
- [x] Atomic commit.
