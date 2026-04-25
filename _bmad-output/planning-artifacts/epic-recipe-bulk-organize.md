<!-- refined via party-mode 2026-04-25 (consolidated) -->
# Epic: Recipe Bulk-Organize — Long-Press Add/Move + Detail-Page Book Picker Redesign

## Overview

Make moving recipes between books — both in bulk from the recipe list and one-at-a-time from the recipe detail page — significantly faster and more honest about intent. Long-press multi-select gains two new actions (`Add to…` and `Move to…`) that work consistently from any list view, with a small disambiguation prompt when the selection spans multiple source books from the global view. The recipe-detail screen replaces today's busy horizontal book scrollbar with a tap-to-reveal horizontal pill row and a "+" pill for creating a new book inline.

## Goal

Lower the cost of re-shelving recipes — graduating a recipe from `Trying Out` to `Favorites` (a tag, not a move — see `epic-recipe-default-books`) or to a real curated book, or sweeping out a backlog into one — to a single deliberate gesture. Preserve single-FK book membership; preserve the existing bulk-archive / create-meal actions; reuse the existing bulk-move backend endpoint.

## End-user flow

1. **User long-presses any recipe** (grid or table view, on home or inside a book) → enters multi-select mode (existing behavior). Selection appbar shows count + Cancel.
2. **User taps additional recipes to add to selection** → existing behavior.
3. **Bottom action bar offers, in order:** existing primary action (Create Meal / Add to Meal — context-sensitive, unchanged), `Add to…` (new), `Move to…` (new), Archive (existing).
4. **User taps `Add to…`** → bottom sheet opens with a list of all the user's books (Trying Out pinned, then user books; Favorites omitted since favoriting is a separate action). Tapping a book moves the selected recipes' `recipe_book_id` FK to that book — a destructive operation today since recipes are single-book — but the action is labeled "Add to" because users think of books as containers, not foreign keys.
   - **Decision:** treat `Add to <book>` as identical to `Move to <book>` from the global "All recipes" view. The action label is the user-facing affordance; the implementation is a single FK swap. Document this clearly in the action's tooltip and undo-toast: "Moved 5 recipes to Favorites. Undo?"
   - This is *not* a copy. If the user wants two copies of the same recipe, they use the existing `Copy` action on the recipe detail page (already shipped).
5. **User taps `Move to…` from inside a book view** → bottom sheet opens; selecting a target book removes the selection from the current book and adds to the target. Toast: "Moved 5 from Mom's Recipes to Favorites. Undo?"
6. **User taps `Move to…` from the global view, with selection spanning multiple source books** → small sheet appears: "*Move from which book?*" with checkboxes for each represented book in the selection ("Mom's Recipes (3)", "Trying Out (2)"). Default: all checked. Confirm → proceed to target picker.
7. **One-tap Undo on every move/add toast** for ~5 seconds; reverses the FK swap atomically (single bulk request to undo).
8. **Recipe detail page (`/recipes/{id}`)**:
   - Today: a horizontal scrollbar of book pills sits permanently above the recipe header (per user's recall — actually a modal `ListView` per recon, not a scrollbar; re-confirm and pick the cleaner replacement).
   - After: a single 📒 book icon next to the recipe title shows the current book name as a small pill. Tapping the icon expands a horizontal scrollable pill row of *all* the user's books, with the current one highlighted. Tapping any pill moves the recipe to that book (toast + Undo, same plumbing as bulk). A trailing "+" pill creates a new book inline (name input → save → recipe lands there).
   - Tapping the book icon again (or anywhere outside) collapses the pill row.

## Frontend changes

- **`home_bulk_action_bar.dart`** — extend `BulkPrimaryAction` enum with `addToBook` and `moveToBook`. Render two new buttons (icon + label) between the existing primary action and Archive. Wire to a new sheet `BookPickerSheet`.
- **New widget `BookPickerSheet`** — bottom sheet with system-pinned Trying Out at top, then user books, then a "+ New book" row at the bottom. Used for both `Add to…` and `Move to…`. Returns `RecipeBook | null`.
- **New widget `MoveSourceDisambiguationSheet`** — only invoked when `Move to…` is triggered from the global "All recipes" view AND the selection spans multiple source books. Renders checkboxes per represented book with selected counts; confirms returns a list of source book ids to remove from.
- **`home_selection_controller.dart`** — extend the action handler with `onAddToBook(bookId)` and `onMoveToBook(bookId, [sourceBookIds])`. Calls into `RecipeService.bulkMoveRecipes(recipeIds, destinationBookId)`.
- **Undo plumbing** — toast widget with action button; on tap, fires the inverse bulk-move (record `(recipeId, sourceBookId)` per recipe at action time so undo can restore each individually). Single bulk-move request for the inverse where all recipes share the same source; otherwise N small calls.
- **`recipe_detail_screen.dart`** — replace the existing modal book picker (lines 341–400 per recon) with:
  - A small 📒 book pill next to the title, default tappable to expand.
  - On expand: a horizontal `ListView` of `_BookPillChip` widgets (current book highlighted with a check + accent border) followed by `_NewBookPill` ("+" with placeholder text "Add to new book").
  - Tapping a pill: moves the recipe via `RecipeService.moveRecipe`, collapses the row, shows the toast.
  - Tapping `+`: opens an inline `TextField` (or a small dialog) to name a new book; on save creates the book and moves the recipe in one combined call (or two sequential — accept the small flicker for v1).
- **Empty-list edge case**: user with only the system Trying Out book sees Trying Out + "+ New book" only.

## Backend changes

- **No schema changes.** All operations are FK swaps.
- **Bulk-move endpoint reuse.** `POST /recipes/bulk/move` already exists (per recon). Confirm it accepts up to 100 ids; the disambiguation flow may issue per-source-book calls if the response shape doesn't tolerate multiple source books in one call. Keep the API surface minimal.
- **Optional: `POST /recipes/bulk/move-with-rollback`** — accepts `{recipe_ids, destination_book_id}` and returns `{moved: [{id, prior_book_id}]}` so the client can construct the undo without re-fetching. If existing endpoint already returns prior book ids, use it; otherwise add the field. Decide in story `recipe-bulk-org-2`.
- **Authorization** on bulk move: every recipe in the request must be owned by the calling user; otherwise the entire request fails (existing behavior — confirm).
- **Performance**: a 100-recipe bulk move should complete in < 500ms server-side (existing pattern, single transaction).

## Infrastructure changes

None.

## Initial design principles (from research + party-mode)

- **Long-press semantics stay identical across views.** From "All recipes" or from a book — the same long-press, the same two new buttons. The disambiguation prompt is the only context-aware variation.
- **`Add to…` and `Move to…` differ in label and toast copy, not in mechanics.** Single-FK reality means both are FK swaps. The labels honor the user's mental model; we don't lie about the destructive nature in the toast.
- **Toast Undo is the safety net, not a confirmation dialog.** Multi-select users are deliberate; intercepting them with a "Are you sure?" modal would be patronizing.
- **Recipe-detail book picker is hidden by default.** The book icon is a tap target, not a permanent strip — addresses the user's complaint that the old horizontal scrollbar was "really busy."
- **No multi-membership.** A recipe is in exactly one book, ever. Favorites is a separate axis (handled in `epic-recipe-default-books`).

## File structure

```
app/lib/features/home/widgets/
  home_bulk_action_bar.dart              # MODIFY — add two buttons
  home_selection_controller.dart         # MODIFY — extend action handlers
  book_picker_sheet.dart                 # NEW
  move_source_disambiguation_sheet.dart  # NEW
  bulk_move_undo_toast.dart              # NEW
app/lib/features/recipes/
  recipe_detail_screen.dart              # MODIFY — replace modal picker
  widgets/recipe_book_pill_row.dart      # NEW
  widgets/new_book_pill.dart             # NEW
app/lib/services/
  recipe_service.dart                    # MODIFY (small) — undo helper if needed
services/api/src/api/v1/recipe/
  bulk_move_recipes.py                   # AUDIT — add `prior_book_id` to response if missing
```

## Stories

### `recipe-bulk-org-1` — Frontend: `Add to…` + `Move to…` actions on long-press bar (single source book)

**Acceptance:**
- `BulkPrimaryAction` enum includes `addToBook` and `moveToBook`; bar renders both as icon-and-label buttons.
- Tapping either opens `BookPickerSheet` listing books with system Trying Out pinned, plus a "+ New book" row.
- `Add to…` and `Move to…` from a single-source-book selection both swap the FK to the chosen target via `RecipeService.bulkMoveRecipes`.
- Toast shows "Moved N recipes to <book>" with a 5s Undo affordance; tapping Undo issues the inverse bulk move.
- Widget + integration tests: long-press → select 3 recipes → Add to → pick book → toast → Undo restores selection.

### `recipe-bulk-org-2` — Backend: prior-book-ids in bulk-move response (if missing)

**Acceptance:**
- Audit `bulk_move_recipes.py`: if response already includes per-recipe prior book id, no change; otherwise extend response to `{ moved: [{ id, prior_recipe_book_id }], moved_count }`.
- Coverage: round-trip test confirms the prior id is correct after the FK swap (DB read before/after).
- 100% line coverage maintained.

### `recipe-bulk-org-3` — Frontend: source-book disambiguation from global view

**Acceptance:**
- When `Move to…` triggered from "All recipes" with selection spanning > 1 source book, `MoveSourceDisambiguationSheet` opens before the destination picker.
- Default: all source books checked.
- User unchecking a source book removes those recipes from the operation.
- After source confirm → destination picker → toast (with breakdown: "Moved 3 from Mom's, 2 from Trying Out → Favorites").
- Single-source case skips the sheet (existing behavior from story 1).

### `recipe-bulk-org-4` — Frontend: recipe-detail book picker — pill row replaces modal

**Acceptance:**
- `recipe_detail_screen.dart` no longer renders the existing modal `ListView` book picker.
- A 📒 book pill next to the title shows the current book name; tapping it expands a horizontal pill row of all books (current highlighted) + a "+" pill at the end.
- Tapping any pill moves the recipe via `RecipeService.moveRecipe`, collapses the row, shows toast + Undo.
- Tapping "+" opens an inline name input; on submit, creates the book and moves the recipe in one combined sequence (acceptable to do as two sequential calls in v1).
- Tapping outside the expanded row collapses it without action.
- Widget tests cover: collapsed state, expanded state, pill tap, "+" tap, outside-tap-collapse.

### `recipe-bulk-org-5` — Regression sweep + e2e

**Acceptance:**
- Existing long-press → archive flow unchanged.
- Existing Create Meal / Add to Meal flow unchanged.
- Bulk move respects authorization (recipes not owned by user → 403, full request fails — current behavior).
- Reactivity: after a bulk move, the source and destination book lists both invalidate via existing `mutationBus` events.
- e2e: select 5 recipes spanning Trying Out + a personal book → Move to Favorites → reload home → confirm all 5 in Favorites filter, none in source books.

## Dependencies

- **Soft:** `epic-recipe-default-books` (Trying Out exists for new users) — bulk-organize works without it but is less interesting since "+ New book" is the only target.
- **Hard:** none.

## Open questions for the user

None — all locked in the 2026-04-25 PRD addendum.

## Lenses (party-mode coverage check)

- **PM (John):** confirmed `Add to…` and `Move to…` are user-facing labels; backend reality is a single FK swap. Toast copy must be honest.
- **UX (Sally):** confirmed disambiguation sheet only fires in the genuinely ambiguous case (one tap clarification, not a mode change).
- **Frontend (Amelia):** confirmed reuse of `BookPickerSheet` between bulk and recipe-detail flows; new toast widget is single-purpose.
- **Backend (Winston):** locked endpoint reuse; only added field is `prior_recipe_book_id` for undo.
- **QA (Quinn):** test plan covers single-source, multi-source, undo, recipe-detail-pill flows.
- **Infra:** None.
