# recipe-defaults-3 — Frontend: switcher pins system books at top with distinct styling

**Epic:** `epic-recipe-default-books`
**Status:** review
**Order in epic:** 3 of 4

## Why

Stories 1 and 2 land the backend primitives — `is_system` column, per-user
seed, default-set on first authed request. The user can now log in and
see a Trying Out book in the API. This story surfaces the System books
distinctly in the Recipe Books screen so the user can reach them in one
tap.

## Scope — files this story touches

**MODIFY**
- `app/lib/features/recipe_books/recipe_books_screen.dart` — render a
  "System" section (Favorites tile + Trying Out tile) above a divider
  before the user-books list; filter the system book out of the
  user-books loop so it only appears in the System section.
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` — hide
  the "Edit" (rename) and "Archive" popup-menu items when the book is
  `is_system=true`. The backend guards from story 1 already 400 the
  request; this is the matching UI affordance change.
- `app/lib/core/router/app_router.dart` — add `/favorites` route.
- `app/test/recipe_books_test.dart` — extend with a widget test that
  proves the System section renders both tiles and that tapping
  Favorites/Trying Out resolves to the correct route.

**NEW**
- `app/lib/features/recipes/favorites_screen.dart` — lightweight list
  view of favorited recipes, fed by the existing `getFavorites()` API
  call. Same pattern as `RecipeBooksScreen` (Stateful widget, retry on
  error, empty state). Tapping a recipe navigates to the recipe detail.
- `_bmad-output/implementation-artifacts/recipe-defaults-3-...md` (this file).
- `_bmad-output/implementation-artifacts/recipe-defaults-3-...-qa-walkthrough.md`.

### Out of scope

- **No favorites-carousel feature parity.** The home screen's favorites
  carousel groups recipes + meals (md-3); the new Favorites screen for
  this story shows only recipes (the `getFavorites()` payload). Adding
  meals is deferred — it's an additive widget-level concern that can
  ship in a follow-up.
- **No "hide system books" preference.** The epic explicitly defers the
  per-user toggle to a follow-up if requested. v1 = always pinned.

## Acceptance criteria

1. **System section header.** RecipeBooksScreen renders a header reading
   "System" above two tiles when at least one system book exists.
2. **Favorites tile.** ❤️ icon + "Favorites" label + tappable; routes to
   `/favorites`.
3. **Trying Out tile.** 📒 icon + "Trying Out" label + recipe-count
   badge (from the API row); tappable; routes to
   `/recipe-books/{trying_out_id}`.
4. **Divider.** A visual separator sits between the System section and
   the user-books list.
5. **System book NOT duplicated.** The user's Trying Out row is rendered
   only in the System section; the user-books list filters
   `is_system=true` rows out so they don't appear twice.
6. **Detail-screen guard.** When `_recipeBook['is_system']` is true,
   the "Edit" and "Archive" items in the recipe-book detail's
   popup-menu are not rendered. Other items (Import URL, etc.) stay.
7. **Favorites screen.** `/favorites` route renders a list of
   favorited recipes via the existing `getFavorites()` call. Tapping a
   recipe navigates to its detail. Empty + error states use the
   existing `EmptyStateWidget` / `ErrorBanner` patterns.
8. **Widget tests.** New tests in `app/test/recipe_books_test.dart`:
   - System section header + tiles render when an `is_system=true`
     book is in the API payload.
   - The system book is NOT rendered in the user-books list section.
9. **Flutter analyzer + tests.** `dart analyze` clean; existing
   `flutter test` suite stays green.

## Risks & mitigations

- **Risk:** existing tests build the screen synthetically without a
  real RecipeBooksScreen instance. **Mitigation:** the new tests
  follow the same synthetic pattern — they don't bring in the live
  screen, just the rendering structure.

- **Risk:** the `/favorites` screen reaches the backend; we don't have
  a real network for unit tests. **Mitigation:** keep the screen
  minimal — its sole responsibility is to render the API result. We
  don't test the network round-trip; we test the rendering logic
  separately if needed (deferred to recipe-list-org epic).

## Definition of done

- [ ] System section rendered with both tiles + divider.
- [ ] Trying Out hidden from the user-books list.
- [ ] Detail screen hides Edit/Archive on `is_system=true`.
- [ ] Favorites screen + route shipped.
- [ ] Widget tests cover the System section rendering.
- [ ] `dart analyze`, `flutter test` green.
- [ ] Sprint-status flipped.
- [ ] QA walkthrough file present.
