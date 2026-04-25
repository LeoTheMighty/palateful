# recipe-bulk-org-3 — Frontend: source-book disambiguation from global view

**Epic:** `epic-recipe-bulk-organize`
**Status:** review
**Order in epic:** 3 of 5

## Why

Story 1 short-circuits multi-source `Move to…` flows by treating the
selection identically to `Add to…` (move every selected recipe regardless
of source). That's correct for the simple case but loses fidelity when
the user actually wants to move only a *subset* of source books — e.g.
"move just the Mom's recipes, leave Trying Out alone".

Story 3 adds the disambiguation prompt: when `Move to…` triggers from
the home global view AND the selection spans more than one source book,
a small modal sheet appears first with one checkbox per represented
source book (default: all checked). The destination picker only opens
after the user confirms the sources. Single-source `Move to…` keeps the
existing fast path (no extra sheet).

`Add to…` skips the prompt unconditionally — the user-facing semantics
are "add these recipes to <book>" regardless of where they currently
live.

## Scope — files this story touches

**NEW**
- `app/lib/features/home/widgets/move_source_disambiguation_sheet.dart`
  — sheet widget + the `SourceBookGroup` value object exposed for the
  caller to construct.
- `app/test/features/home/move_source_disambiguation_sheet_test.dart`
  — widget tests.
- `_bmad-output/implementation-artifacts/recipe-bulk-org-3-frontend-source-book-disambiguation-from-global-view.md`
  (this file).
- `_bmad-output/implementation-artifacts/recipe-bulk-org-3-qa-walkthrough.md`
  (QA checklist).

**MODIFY**
- `app/lib/features/home/home_screen.dart` — `_handleBookMove` now
  computes per-source-book groups, shows
  `MoveSourceDisambiguationSheet` when `verb == BookMoveVerb.move` and
  there are ≥ 2 source books, trims the prior-map to the user's
  surviving selection, and feeds the resulting count breakdown into
  the toast.
- `app/lib/features/home/widgets/bulk_move_undo_toast.dart` — accept
  an optional `breakdown` string. When supplied (multi-source case),
  the toast reads `Moved <breakdown> → <destinationName>`. Single-source
  callers pass `null` and keep the original `Moved N to <book>` copy.
- `app/test/features/home/bulk_move_undo_toast_test.dart` — extend the
  existing tests with a multi-source breakdown case.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  this story `backlog → done`.

### Out of scope

- Recipe-detail pill row (story 4).
- Backend-side per-source-book bulk endpoints. The existing
  `BulkMoveRecipes` endpoint already validates per-recipe source
  membership independently, so a single API call still suffices even
  after disambiguation.

## How

1. **Group recipes by `recipe_book_id`** using the home content cache
   that `_findRecipe(id)` already exposes.
2. **Skip the prompt** when `verb == BookMoveVerb.add` or when the
   group count is ≤ 1.
3. **Show `MoveSourceDisambiguationSheet`** with one
   `SourceBookGroup` per source. Default-check every group; uncheck
   dropping the recipes from that source.
4. **Trim the prior-map** to the kept group ids before continuing into
   `BookPickerSheet` and the bulk-move call.
5. **Toast** reads `"Moved 3 from Mom's, 2 from Trying Out → Favorites"`
   when multi-source, falls back to `"Moved N to <book>"` when single.

## Acceptance

- Single-source `Move to…` from any view skips the prompt (story 1
  fast path preserved).
- Multi-source `Move to…` from "All recipes" opens the prompt;
  unchecking a source removes its recipes from the operation.
- Confirm with zero sources is impossible — the `Continue` button is
  disabled.
- The destination picker is the same `BookPickerSheet` story 1 ships.
- Toast surfaces a per-source breakdown in the multi-source case.
- `Add to…` still moves every selected recipe regardless of source.

## Test plan

- Widget: `MoveSourceDisambiguationSheet` rendering, default state,
  uncheck → trim, Cancel → null, all-unchecked disables Continue.
- Widget: `bulk_move_undo_toast` multi-source breakdown branch.
- e2e (deferred to story 5): full flow from long-press across two
  books → Move to → uncheck one → confirm → destination picker → toast
  reads breakdown → Undo restores both groups.
