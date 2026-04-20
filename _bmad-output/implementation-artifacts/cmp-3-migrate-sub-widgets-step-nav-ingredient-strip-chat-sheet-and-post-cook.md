# cmp-3 — Migrate cook-mode sub-widgets to CookModeTheme

**Status:** review
**Epic:** epic-cook-mode-polish

## Summary

Migrates all four cook-mode sub-widgets off `colorScheme.primary/tertiary`
and `appColors.success/textTertiary/outlineVariant` onto `CookModeTheme`
tokens.

- **step_navigator.dart**: pill + nav-button colors use `cookAccent`,
  `cookCompleted`, `cookSurfaceDim`, `cookOnAccent`, `cookOnCompleted`.
  Shadow uses `cookShadow`. Each pill now emits a `Semantics(label:
  'Step N, current|completed|upcoming')` node so TalkBack/VoiceOver
  announce state transitions. **Pill "completed" render is gated on
  `index != currentStep`** — the current pill never shows a green check,
  regardless of set membership (reinforces cmp-4 AC4).
- **ingredient_strip.dart**: checked chip uses `cookCompleted` +
  `cookOnCompleted`; unchecked uses `cookSurfaceDim` + `cookOnSurface`;
  borders use `cookDivider`; counter badge uses `cookAccent`. Compact /
  expanded animation + haptics unchanged.
- **cook_mode_chat_sheet.dart**: sheet background `cookSurface`, input
  row `cookSurface` (was raw `primary`), input fill `cookSurfaceDim`,
  focused border `cookAccent`, assistant bubble
  `cookAccent.withValues(alpha: 0.12)`, user bubble filled `cookAccent`
  + `cookOnAccent` text.
- **post_cook_feedback_sheet.dart**: stars use `cookAccent`, notes field
  borders `cookDivider`/`cookAccent`, Save button `cookAccent` +
  `cookOnAccent`. No behaviour change.

## Regression test harness updates

The five existing Epic 6 tests pumped cook-mode widgets in
`MaterialApp()` without a theme. The new `context.cookModeTheme`
getter `assert`s in debug when the extension is missing, which breaks
those tests. Added `theme: AppTheme.light()` to:

- `app/test/cook_mode_test.dart` (3 pumps: IngredientStrip,
  StepNavigator x2)
- `app/test/cook_mode_gesture_test.dart` (2 pumps: StepNavigator,
  IngredientStrip)
- `app/test/post_cook_feedback_test.dart` (1 pump: buildSheet helper)

## Grep gate

```
$ rg "colorScheme\.(primary|tertiary)" app/lib/features/recipes/cook_mode/
(no matches)
```

AC6 satisfied. A dedicated `app:grep-cook-mode-tokens` lint target is
out of scope for this story — the manual check above is sufficient for
the epic's surface area. Future migrations can add the lint when there
are more cook-mode widgets to keep tidy.

## File list

- `app/lib/features/recipes/cook_mode/widgets/step_navigator.dart` — modified
- `app/lib/features/recipes/cook_mode/widgets/ingredient_strip.dart` — modified
- `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` — modified
- `app/lib/features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart` — modified
- `app/test/cook_mode_test.dart` — test-harness theme wire-in
- `app/test/cook_mode_gesture_test.dart` — test-harness theme wire-in
- `app/test/post_cook_feedback_test.dart` — test-harness theme wire-in
