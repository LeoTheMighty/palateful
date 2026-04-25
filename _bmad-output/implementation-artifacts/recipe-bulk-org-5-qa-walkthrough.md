# recipe-bulk-org-5 — QA walkthrough (regression sweep)

**Story:** Regression sweep + e2e for `epic-recipe-bulk-organize`.

This is a manual sweep over the surfaces stories 1–4 touched. Walk
through the lists below; treat any unexpected behavior as a regression
bug rather than ticking the box.

## Setup

- Logged-in user, fresh launch.
- ≥ 6 recipes split: 3 in `Trying Out`, 2 in a personal book ("Mom's"),
  1 in another personal book ("Favorites" or any third writable book).
- Optional: a Meal in the home grid.

## A — Existing flows must be unchanged

### Long-press → Archive

- [ ] Long-press a recipe → multi-select. Tap a second recipe.
- [ ] Bulk bar shows `Create Meal` + `Add to` + `Move to` + Archive.
- [ ] Tap Archive → confirmation dialog → Archive. Snackbar
      "Archived 2 items".
- [ ] Open Archive screen → both recipes visible. Restore one. Home
      grid reflects the restore without a manual refresh.

### Create Meal / Add to Meal

- [ ] Long-press recipe A and B (no Meal in selection) → primary slot
      reads `Create Meal`. Tap → CreateMealSheet opens prefilled.
- [ ] Cancel out. Long-press a Meal then a recipe → primary slot
      reads `Add to "<meal name>"`. Tap → recipe is added.

### Recipe-book detail bulk move

- [ ] Open a personal book → long-press 2 recipes → tap Move →
      pick another writable book. Snackbar "2 recipes moved to <book>".
- [ ] The detail screen for the source book shows the moved recipes
      gone after a brief pause (no manual refresh needed).

## B — New flows from stories 1, 3, 4

### Bulk Add-to / Move-to (single source)

- [ ] On Home, long-press 3 recipes from the same book → tap
      `Add to` → BookPickerSheet opens with Trying Out pinned + user
      books + "+ New book". Pick a book. Snackbar reads
      `Moved 3 recipes to <book>`. Tap Undo within 5 s → recipes
      restore.

### Multi-source disambiguation (story 3)

- [ ] On Home (global view), long-press 1 Trying Out recipe + 1 Mom's
      recipe → tap `Move to`. Disambiguation sheet opens titled
      "Move from which book?" with both checkboxes ticked.
- [ ] Uncheck Mom's → only Trying Out recipe moves through. Continue,
      pick destination, snackbar reads `Moved 1 from Trying Out → <book>`
      (no breakdown when only one source kept).
- [ ] Repeat: keep both checked. Confirm → snackbar reads
      `Moved 1 from Trying Out, 1 from Mom's → <book>`. Undo restores
      both.

### Recipe-detail pill row (story 4)

- [ ] Open a recipe (`can_edit` = true). Below the title (or lineage
      badge), a single 📒 pill shows the current book name. The
      popup-menu "Move to Book…" item is **gone**.
- [ ] Tap the pill → expanded row shows every writable book with
      Trying Out pinned, current pill highlighted, "+ New book"
      trailing.
- [ ] Tap a different pill → recipe moves; pill row collapses; toast
      reads `Moved 1 recipe to <book>` with Undo.
- [ ] Re-open the recipe (or pull-to-refresh) → the new book name is
      now the collapsed pill's label.
- [ ] Tap the pill again, then "+ New book". Type a name → toast +
      Undo land in the new book.

## C — Authorization

- [ ] As a viewer on a shared book, open the recipe detail → the pill
      row is hidden.
- [ ] (If feasible) Try `POST /v1/recipes/bulk/move` from a CLI with a
      recipe id you don't own → 403.

## D — Reactivity (Locked Decision #2)

- [ ] After any home bulk-move, both source and destination book
      detail screens reflect the move within ~2 s without a manual
      pull-to-refresh.
- [ ] After a recipe-detail move, the home grid reflects the new
      `recipe_book_id` after the next render frame.

## Automated coverage

- [ ] `flutter test test/features/home test/features/recipes
      test/features/recipe_books` — all green.
- [ ] `npx nx run api:test -- tests/test_recipe.py::TestBulkMoveRecipes` —
      all 7 green.

If any of these regress, capture a screenshot/log and file a follow-up
under the epic before flipping it `done`.
