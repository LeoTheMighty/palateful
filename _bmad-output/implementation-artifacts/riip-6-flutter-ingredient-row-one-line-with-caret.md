# Story riip-6: Flutter — `StructuredIngredientRow` one-line + caret + auto-expand

**Status:** done
**Epic:** epic-review-import-ingredient-polish

## Goal
Every ingredient row across Review Import, the recipe wizard, and recipe
edit now fits on one tap-target line. Notes + the optional toggle sit
behind a caret-expansion row that auto-opens when those fields have
content. Layout math is locked for iPhone SE 1st-gen (320 × 568).

## Scope (from epic)
- **Value-object changes** (`IngredientRowData`):
  - New `expanded: bool?` field with getter that auto-defaults to
    `true` when notes is non-empty OR is_optional is true. `copyWith`
    preserves explicit overrides via the sentinel pattern so manual
    collapse persists across auto-save rebuilds.
  - `hasHiddenContent` getter returns true when caret is collapsed AND
    content is hidden behind it — powers the dot indicator.
  - New `pendingReviewIngredient: bool` field seeded for riip-7.
- **Row layout rewrite**:
  - Main row: `[qty: 48] [unit: 72] [name: flex] [caret: 40] [delete: 40]`
    inside a single `SizedBox(height: 48)` + `Row`.
  - Expansion row: `[notes: flex] [optional]` inside an `AnimatedSize`
    with a 150 ms ease-out curve. Renders `SizedBox.shrink()` when
    collapsed.
  - `_CaretButton` Stack overlays a 7-pt `colorScheme.tertiary` dot at
    top-right when `hasHiddenContent` is true.
  - Debug-build `assert(constraints.maxWidth >= 320)` inside a
    `LayoutBuilder` shouts loud in dev; release still renders (clipping
    accepted) per the epic principle.
  - Row-level `Semantics` label reads
    "Ingredient {qty} {unit} {name}{, optional}{, notes: {notes}}.".
- **Qty paste handler** (riip-5 AC7): pastes like "2 tablespoons" into
  qty are stripped to the first token, snackbar "Trimmed to quantity
  only — unit dropped" fires. Mixed fractions like "1 1/2" are
  preserved.
- **SessionAliasMap wiring**: `aliasMap` is forwarded to the embedded
  `UnitInput` so the row (and the three surfaces that consume it) can
  continue to coerce on blur. The parameter is optional and defaults
  to DI-driven `getIt<SessionAliasMap>()`.

## File List
- `app/lib/features/recipes/widgets/structured_ingredient_row.dart` —
  major rewrite (one-line layout, caret, expansion row, value-object
  update, qty paste handler, Semantics)
- `app/test/features/recipes/widgets/structured_ingredient_row_test.dart` —
  rewritten (existing tests migrated to the new widget; 6 new tests
  for auto-expand / manual collapse persistence / dot indicator /
  locked widths)

## Notes
- `_RowLayout` constants (`qty=48, unit=72, caret=40, delete=40`)
  are asserted in the "locked widths" widget test so a future layout
  tweak can't silently regress the iPhone-SE budget.
- `notes: ' '` (a single space) is still considered "non-empty" —
  if the caller wants a blank row they pass `notes: null`. This is a
  useful test seam for existing tests that want to pre-expand the row
  without seeding real notes content.

## QA walkthrough
See `_bmad-output/implementation-artifacts/riip-6-qa-walkthrough.md`.
