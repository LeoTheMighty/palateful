# recipe-bulk-org-1 — Frontend: `Add to…` + `Move to…` actions on long-press bar

**Epic:** `epic-recipe-bulk-organize`
**Status:** review
**Order in epic:** 1 of 5

## Why

Today the home long-press bulk bar only does Create Meal / Add to Meal /
Archive. Re-shelving a backlog of recipes into a curated book is a
multi-tap-per-recipe slog (open detail → menu → Move → pick → repeat).

Story 1 lands the two missing primary affordances on the home bulk bar:

- **`Add to…`** — single-FK swap, but labeled "Add to" because that's the
  user's mental model when they're standing on the global view.
- **`Move to…`** — the same FK swap, labeled "Move" when the source book
  is unambiguous (selection inside one source book or the global view
  with a single source).

Multi-source `Move to…` (selection from "All recipes" spanning multiple
source books) is deferred to story 3 — story 1 short-circuits to the
same Add-style flow there so the buttons are functional immediately.

The recipe-book detail screen already has `_bulkMove`; this story does
not touch it (regression confirmed in story 5). The new picker sheet is
shared infrastructure for story 4 (recipe-detail pill row).

## Scope — files this story touches

**NEW**
- `app/lib/features/home/widgets/book_picker_sheet.dart` — bottom sheet
  with system books pinned, then user books, then a "+ New book" row.
  Used here and in story 4. Returns `Map<String, dynamic>?`.
- `app/lib/features/home/widgets/bulk_move_undo_toast.dart` — small
  helper that shows a SnackBar with an "Undo" action that fires the
  inverse bulk-move.
- `app/test/features/home/book_picker_sheet_test.dart` — widget test.
- `app/test/features/home/bulk_move_undo_toast_test.dart` — widget test.
- `_bmad-output/implementation-artifacts/recipe-bulk-org-1-frontend-add-to-and-move-to-actions-on-long-press-bar.md`
  (this file).
- `_bmad-output/implementation-artifacts/recipe-bulk-org-1-qa-walkthrough.md`
  (QA checklist).

**MODIFY**
- `app/lib/features/home/widgets/home_bulk_action_bar.dart` — add
  `onAddToBook` and `onMoveToBook` callbacks; render two new outlined
  buttons between the primary slot and Archive when the selection has
  ≥1 recipe and zero meals.
- `app/lib/features/home/home_screen.dart` — wire `_handleAddToBook`
  and `_handleMoveToBook` (capture per-recipe prior book id from
  `_findRecipe`, open `BookPickerSheet`, dispatch through
  `RecipeBookService.bulkMoveRecipesByPriorBook`, show undo toast).
- `app/lib/features/recipe_books/services/recipe_book_service.dart` —
  new `bulkMoveRecipesByPriorBook(map, destinationBookId)` helper that
  emits one `RecipeMoved` per recipe with its real prior book id.
- `app/test/features/home/home_bulk_action_bar_test.dart` — extend with
  Add-to / Move-to visibility cases.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  this story `backlog → done`.

### Out of scope

- Multi-source disambiguation sheet (story 3).
- Recipe-detail pill row (story 4).
- Backend response augmentation with `prior_recipe_book_id` (story 2 —
  client captures prior ids itself today).

## How

1. **`BookPickerSheet`** — `static Future<Map<String, dynamic>?> show(BuildContext)`
   reads `recipeBooksProvider`, filters to `user_role in {owner, editor}`,
   sorts `is_system` desc then `last_opened_at` desc. Trailing
   `_NewBookRow` opens an inline `AlertDialog` with a `TextField`; on
   submit, calls `RecipeBookService.createRecipeBook({name})`, then pops
   the sheet with the new book map.
2. **Undo toast** — `showBulkMoveUndoToast(context, count, destName, onUndo)`.
   5-second SnackBar; tapping Undo schedules the inverse via the caller's
   closure (closure captures the prior-book-id map).
3. **Bar buttons** — two outlined `_BookActionButton`s with
   `Icons.drive_file_move_outlined` (Move) and
   `Icons.add_box_outlined` (Add). Hidden when `selection.totalSelected == 0`
   or `selection.selectedMealIds.isNotEmpty`. Disabled while
   `isWorking` is true.
4. **Handlers in `home_screen.dart`**:
   - Resolve `priorMap = {recipeId → recipe_book_id}` from
     `_findRecipe(id)`.
   - `await BookPickerSheet.show(...)`. If null → bail.
   - Call `RecipeBookService.bulkMoveRecipesByPriorBook(priorMap, destId)`.
   - Show toast: `Moved N recipes to <book>`.
   - Undo callback groups `priorMap` by source-book and issues one bulk
     move per group back. Idempotent on re-tap of the bar.
5. **Service helper** — `bulkMoveRecipesByPriorBook(map, destinationBookId)`
   issues one `bulkMoveRecipes` API call (the backend already validates
   per-recipe source membership) and emits one `RecipeMoved` event per
   recipe with the right `oldBookId`.

## Acceptance

- Bulk bar shows `Add to…` and `Move to…` whenever selection has
  ≥1 recipe and zero meals.
- Tapping either opens `BookPickerSheet`; system books pin to top.
- Confirm with a target → moves all selected recipes; toast reads
  "Moved N to <book>" and exposes a 5s Undo.
- Undo restores each recipe to its original book.
- "+ New book" row creates a book inline and lands the selection there.
- Existing Archive / Create Meal / Add to Meal flows unchanged.

## Test plan

- Widget: bar visibility (recipes only / mixed / meal only).
- Widget: `BookPickerSheet` order (system pinned, "+ New book" tail).
- Widget: undo toast presence + tap → invokes onUndo closure.
- Integration (deferred to story 5 e2e): full select → move → undo loop
  against a fake `ApiClient`.
