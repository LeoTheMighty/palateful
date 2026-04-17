# Story bugs-imp-ing-2: StructuredIngredientRow shared widget + fraction parser

Status: done

## Story

As a user editing an ingredient in any screen,
I want quantity, unit, name, notes, and an optional toggle as separate fields,
so that I can see and correct each piece independently — instead of staring
at a single mashed text field that hid them.

## Context

This is the keystone widget the epic depends on. Story 3, 4 each consume it.
Parent owns a `List<IngredientRowData>` and a stable `key` per row; the
widget is value-in / callback-out (no externally-owned controllers) so
insert/delete/reorder at the parent level stays clean (no controller leaks,
no stale focus).

The fraction parser mirrors Python's `format_quantity` (`Fraction.limit_denominator(8)`)
so server-display and client-input round-trip identically. The existing
`quantity_formatter.dart` uses a hardcoded-fraction list which does not
match `limit_denominator(8)` exactly; this story introduces a new
`fraction_parser.dart` with a correct algorithm. `quantity_formatter.dart`
stays where it is for now to avoid touching callers outside this epic;
follow-up consolidation is a P2 opportunity.

## Acceptance Criteria

1. `IngredientRowData` value object + `StructuredIngredientRow` widget.
   Widget owns controllers internally; parent only sees value + callback.
2. Layout: row-1 = `[Qty 64px][Unit 96px][Name flex]`, row-2 =
   `[Notes flex][Optional toggle]`. Trash icon on row-1 far right with ≥24px
   separation from the optional toggle (rows are separate so that is
   naturally satisfied).
3. Quantity accepts integers, decimals, fractions (`1/2`, `1 1/2`). Uses
   `TextInputType.text` (iOS keyboard needs `/`). Helper text: `e.g. 1/2 or 0.5`.
4. Empty quantity/unit/name are allowed; placeholders `Qty`/`Unit`/`Name`.
5. Fits iPhone SE 1st-gen width (320px) without horizontal overflow.
6. Delete row fires an `onDeleteRequest` callback; parent handles
   snackbar-undo (widget stays value-in / callback-out, the undo
   state belongs to the parent list).
7. Widget tests: populated, empty, legacy (name only), edit each field,
   fraction parse round-trip, optional toggle, delete callback fires.
8. Optional toggle `Semantics(label: 'Mark <name> as optional')`.
9. New `app/lib/core/utils/fraction_parser.dart` with
   `parseFraction(String?)` and `formatFraction(double)`; format uses
   `limit_denominator(8)` algorithm.
10. Test coverage on fraction parser: `0`, `1`, `0.5`, `0.333`, `0.1`,
    `1.25`, `2.5`, `1/3`, `2 1/4`, malformed inputs.

## Design Notes

- **Snackbar-undo belongs to the parent.** The widget fires a delete
  callback, and the parent (list-owning screen) decides whether to show
  a snackbar and how to restore. This keeps the widget dumb and
  testable without MaterialApp/ScaffoldMessenger scaffolding.
- **Controller lifecycle**: 3 `TextEditingController`s (qty, name, notes)
  owned internally, recreated only when the widget is first mounted.
  Quantity text is whatever the user typed; on focus loss we parse + format.
- **Fraction display on load**: when loaded with a numeric value, format
  to `"1/2"` etc. for display. When the user types, keep the raw text
  until blur (so `1/` doesn't get auto-closed mid-typing).

## Key Files

- Create: `app/lib/features/recipes/widgets/structured_ingredient_row.dart`
- Create: `app/lib/core/utils/fraction_parser.dart`
- Test: `app/test/features/recipes/widgets/structured_ingredient_row_test.dart`
- Test: `app/test/core/utils/fraction_parser_test.dart`
