# Story riip-7: Flutter — `IngredientRowStateBadge`

**Status:** done
**Epic:** epic-review-import-ingredient-polish

## Goal
Small ✨ badge on ingredient rows whose canonical ingredient was
auto-created by the find-or-create path — so Leo knows when a new item
joined his pantry catalog.

## Scope (from epic)
- New `IngredientRowStateBadge` widget rendering
  `Icons.auto_awesome` at 14 pt in `colorScheme.primary`.
  (The epic asks for `ImportStateColors.inProgress`; that theme
  extension ships with ahr-6 which is still backlogged. `primary` is
  a semantically-equivalent placeholder; swap the literal once the
  extension lands.)
- Tap opens a bottom-sheet explainer with copy
  `"'{name}' was added to your catalog for review. You can rename or
  merge it later in Settings › Pantry."`.
- `StructuredIngredientRow` renders the badge between the name field
  and the caret when `value.pendingReviewIngredient == true`.
- `ingredient_edits_mapping.dart` (the shared JSON ↔
  `IngredientRowData` converter used by Review Import, the wizard, and
  recipe edit) now reads `pending_review_ingredient` off each
  ingredient entry and forwards it to the row value.

## File List
- `app/lib/features/recipes/widgets/ingredient_row_state_badge.dart` — new
- `app/lib/features/recipes/widgets/structured_ingredient_row.dart` —
  modified (render the badge when flag true)
- `app/lib/features/recipes/add_recipe/ingredient_edits_mapping.dart` —
  modified (read `pending_review_ingredient` from JSON)
- `app/test/features/recipes/widgets/ingredient_row_state_badge_test.dart` —
  new (5 tests: hidden when false, visible when true, tap-to-open
  bottom-sheet, unnamed fallback copy, semantic button label)

## Notes
- The badge consumes a tap-target ≥28pt via inner `Padding(8)` — the
  epic's 40pt is for the caret/delete; the badge is inline-small on
  purpose so it doesn't crowd the name field.
- The bottom-sheet `showDragHandle: true` is inherited from
  `Theme.of(context).bottomSheetTheme`; works on both phone and tablet.
- Since `pendingReviewIngredient` already lives on `IngredientRowData`
  (added in riip-6), no new value-object field is introduced here.

## QA walkthrough
See `_bmad-output/implementation-artifacts/riip-7-qa-walkthrough.md`.
