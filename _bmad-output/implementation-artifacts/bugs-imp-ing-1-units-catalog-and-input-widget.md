# Story bugs-imp-ing-1: Curated units catalog + UnitInput dropdown widget

Status: done

## Story

As a user editing ingredient units anywhere in the app,
I want a dropdown of common units with a free-text fallback,
so that I pick "cup" in two taps but can still type "stalk" when I need to.

## Context

Epic `epic-bugs-import-structured-ingredients` wants one shared structured row
used by Review Import, the recipe wizard, and recipe edit. The row needs a
consistent unit picker. Today there is no shared unit widget: the wizard uses a
single text input; Review Import shows only `text` and hides unit entirely.

This story lands the foundation: the curated catalog constant and the
`UnitInput` widget. Story 2 (`StructuredIngredientRow`) composes over it.

## Acceptance Criteria

1. `app/lib/core/constants/ingredient_units.dart` exports `kCuratedUnits`
   with units in intentional order: `cup`, `tbsp`, `tsp`, `oz`, `fl oz`, `ml`,
   `l`, `g`, `kg`, `lb`, `each`, `pinch`, `dash`, `clove`, `slice`.
2. `UnitInput` widget opens a dropdown on focus, filters as the user types,
   and shows `Add custom: "<typed>"` when the typed text doesn't match any
   curated unit. Helper-text footer reads
   `Custom units apply to this ingredient only`.
3. Selecting a curated unit sets the value to the canonical short form.
4. Accepts initial value = curated, custom, or `null`; renders for all three.
5. Empty value renders `"Unit"` placeholder.
6. Widget tests cover: render-curated, render-custom, render-null,
   type-to-filter, custom-entry creation, selection callback fires.
7. Keyboard-accessible and screen-reader labeled `Unit selector`.

## Implementation Notes

- The widget is a thin `TextFormField` + overlay menu. No `Autocomplete`
  dependency; keeping it handwritten keeps behavior predictable (custom-entry
  row, helper footer, semantics tweaks).
- `FocusNode` drives the overlay open/close; typing filters the list via a
  `ValueNotifier<String>`; selecting closes the overlay and fires `onChanged`.
- Semantics wrapper tags the field `Unit selector` for VoiceOver.

## Key Files

- Create: `app/lib/core/constants/ingredient_units.dart`
- Create: `app/lib/features/recipes/widgets/unit_input.dart`
- Test: `app/test/features/recipes/widgets/unit_input_test.dart`
