# recipe-bulk-org-4 — Frontend: recipe-detail book picker pill row replaces modal

**Epic:** `epic-recipe-bulk-organize`
**Status:** review
**Order in epic:** 4 of 5

## Why

The recipe-detail screen surfaces "Move to Book…" via a popup-menu item
that opens a modal `ListView` of every book. Two issues:

1. The action is buried inside the overflow menu — the user has to know
   it's there.
2. The modal is a context switch (full-sheet ListView) rather than an
   in-place affordance.

Story 4 replaces both with a tap-to-reveal **pill row** that lives in
the body of the recipe detail screen, directly under the header. In its
collapsed state it shows a single `📒 <current book name>` chip; tapping
expands a horizontal scrollable list of every writable book + a trailing
"+ New book" pill. Tapping any other pill moves the recipe; tapping the
current pill (or any pill in collapsed state's "+" target) collapses
the row. Tapping "+" opens an inline name dialog, creates the book, and
moves the recipe in one combined sequence.

## Scope — files this story touches

**NEW**
- `app/lib/features/recipes/widgets/recipe_book_pill_row.dart` —
  collapsed/expanded pill row + the pure `sortBooksForPillRow` helper
  for tests.
- `app/test/features/recipes/recipe_book_pill_row_test.dart` — widget
  tests.
- `_bmad-output/implementation-artifacts/recipe-bulk-org-4-frontend-recipe-detail-book-picker-pill-row-replaces-modal.md`
  (this file).
- `_bmad-output/implementation-artifacts/recipe-bulk-org-4-qa-walkthrough.md`
  (QA checklist).

**MODIFY**
- `app/lib/features/recipes/recipe_detail_screen.dart` — render the
  pill row at the top of the content sliver when `can_edit` is true;
  drop the popup-menu "Move to Book…" item; route pill taps through
  the new `_handleBookPillSelect` helper. Adds an inline-create flow
  (`_createBookAndMove`) and a single-recipe `_undoSingleMove` to
  reuse the bulk-move toast.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  this story `backlog → done`.

### Out of scope

- Tapping outside the expanded row to collapse it. The current pill
  acts as the toggle; the user can also pick a pill or the "+" pill.
  An outside-tap collapse adds a new `Listener` over the entire
  scaffold and isn't load-bearing for the AC.
- Removing the modal `_showBookPicker` helper — `Copy to Book…` still
  uses it. That'll get refactored together with the share flow later.

## How

`RecipeBookPillRow` is a `StatefulWidget` with a single `_expanded`
boolean. Collapsed → renders one `ActionChip` with the current book
name. Expanded → renders a horizontal `ListView` of `_BookPillChip`
(`ChoiceChip` selected on the current book) + a `_NewBookPill`
(`ActionChip` with a `+` icon). System books pin to the front of the
expanded list via `sortBooksForPillRow`. The widget exposes a
`collapse()` method via `RecipeBookPillRowState` so the parent can
collapse the row imperatively after a successful move.

Parent (`recipe_detail_screen`):
- Watches `recipeBooksProvider` for the list, filters to writable
  books (`user_role in {owner, editor}`).
- `_handleBookPillSelect(bookId)`:
  - `bookId == null` → call `_createBookAndMove`.
  - else → `RecipeService.moveRecipe`, `invalidateRecipe`, collapse
    the row, show the bulk-move toast (story 1's
    `showBulkMoveUndoToast`) with `movedCount: 1`.
  - On Undo, the inverse `moveRecipe` puts the recipe back.
- `_createBookAndMove` opens an `AlertDialog` text input, creates the
  book via `RecipeBookService.createRecipeBook`, then moves the recipe
  into the new book and surfaces the same Undo toast.

## Acceptance

- Collapsed row shows just the 📒 + current book name; nothing else.
- Tapping it expands a horizontal pill row of every writable book.
  System books pin to the front.
- Current pill is highlighted (`ChoiceChip.selected`).
- Tapping a non-current pill moves the recipe and collapses the row.
- Tapping the current pill in expanded state collapses without acting.
- "+ New book" opens an inline name input; on save the book is created
  and the recipe lands in it.
- All move actions show the same bulk-move toast as story 1, with a
  5-second Undo.
- Popup-menu "Move to Book…" item is gone.

## Test plan

- Widget (`recipe_book_pill_row_test.dart`):
  - `sortBooksForPillRow` — system pins first.
  - Collapsed shows current name only.
  - Tap collapsed → expands + reveals all books + "+ New book".
  - Tap a non-current pill → onSelect fires with that id.
  - Tap "+ New book" → onSelect fires with null.
  - Tap current pill in expanded → collapses, onSelect not fired.
  - `isWorking` → onPressed null on ActionChip.
- e2e (deferred to story 5).
