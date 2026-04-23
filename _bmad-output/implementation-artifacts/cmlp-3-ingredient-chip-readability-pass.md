# cmlp-3 — Ingredient chip readability pass

Status: done

## Summary

The `_IngredientChip` now renders quantity and name as separate Text
widgets stacked vertically, both at 14px (w600 for the quantity in
`cookAccent`, w500 for the name in `cookOnSurface`). The chip body is
wrapped in a `ConstrainedBox(minWidth: 72, maxWidth: 160)` — not
`IntrinsicWidth`, which would force a layout pass per child inside the
`Wrap` and bloat cost at 30+ ingredient meals. Dead `isCompact` param
is gone.

## Changes

- `app/lib/features/recipes/cook_mode/shared/widgets/ingredient_strip.dart`
  — refactored `_IngredientChip` to:
  - Drop the `isCompact` param (dead after cmlp-2).
  - Wrap the chip body in `ConstrainedBox(minWidth: 72, maxWidth: 160)`.
  - Render quantity as 14px w600 (`cookAccent` or `cookOnCompleted`).
  - Render name as 14px w500 (`cookOnSurface` or `cookOnCompleted`)
    with `maxLines: 2`, `overflow: ellipsis`, `softWrap: true`.
  - Stack quantity + name vertically (Column) inside the chip so the
    name has the full 160dp chip width to wrap into. Row with Flexible
    gave Row-level horizontal overflow at TextScaler 2.0 on long
    ingredient names; a vertical stack dodges that.
  - Keep strikethrough on both texts in the checked state (matches
    today's kitchen-light legibility pattern).
  - Updated callers in both `_buildExpandedGrid` branches to drop the
    `isCompact` kwarg.

- `app/test/cook_mode_test.dart` — added `cook_mode_theme.dart` import
  and three cmlp-3 tests:
  - `chip renders 14px w500 name + 14px w600 quantity in cookAccent`
    — reads styles via `tester.widget<Text>`.
  - `chip tree contains no IntrinsicWidth`.
  - `long name at TextScaler 2.0 does not overflow`
    (`tester.takeException()` is `null`).
  - Restored the stricter `find.text('Garlic')` assertion (name is now
    its own Text).

- `app/test/cook_mode_resume_test.dart` — restored the stricter
  `find.text('Ingredient 1')` tap target (cmlp-3 splits the chip body).

## Acceptance criteria

- At `TextScaler(2.0)` a long name like "Freshly ground black
  peppercorns" does not raise a `RenderFlex overflowed` warning. ✓
  (new test in `cook_mode_test.dart`).
- Quantity renders at 14px w600 `cookAccent` in an unchecked chip. ✓
  (new test reads the style via `tester.widget<Text>`).
- `IntrinsicWidth` is NOT used anywhere in the refactored chip tree. ✓
  (new test asserts `findsNothing`).
- No source-tag pill visible anywhere — `find.textContaining('from ', findRichText: true)`
  returns `findsNothing` within the chip tree. ✓ (the pill code path
  was deleted in cmlp-2; the chip no longer renders any per-chip
  `from X` text).
- Manual visual check in light + dark + system themes is deferred to
  QA walkthrough (no golden baseline exists).

## File list

Modified:
- `app/lib/features/recipes/cook_mode/shared/widgets/ingredient_strip.dart`
- `app/test/cook_mode_test.dart`
- `app/test/cook_mode_resume_test.dart`
