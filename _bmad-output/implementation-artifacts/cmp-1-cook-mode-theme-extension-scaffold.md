# cmp-1 — CookModeTheme ThemeExtension scaffold

**Status:** review
**Epic:** epic-cook-mode-polish

## Summary

Scaffold a new `CookModeTheme` `ThemeExtension` in
`app/lib/core/theme/cook_mode_theme.dart`, defining the 13 cook-mode
tokens (`cookSurface`, `cookSurfaceDim`, `cookOnSurface`, `cookAccent`,
`cookOnAccent`, `cookProgress`, `cookCompleted`, `cookOnCompleted`,
`cookTimer`, `cookError`, `cookOffline`, `cookDivider`, `cookShadow`).
Provides `.light()` / `.dark()` factories, `copyWith`, `lerp`, and a
`BuildContext.cookModeTheme` getter. Register on both `AppTheme.light()`
and `AppTheme.dark()`. No existing cook-mode widget is modified — the
migration happens in cmp-2 and cmp-3.

Documented WCAG AA contrast ratios for each text-on-surface pair in
the doc-comment; a unit test numerically asserts ≥4.5:1 on the three
pairs called out by AC7.

## Acceptance Criteria

- AC1: `CookModeTheme extends ThemeExtension<CookModeTheme>` with 13
  tokens + `copyWith` + `lerp`.
- AC2: `CookModeTheme.light()` and `CookModeTheme.dark()` factories.
- AC3: Registered on both `AppTheme.light().extensions` and
  `AppTheme.dark().extensions`.
- AC4: `BuildContext.cookModeTheme` falls back to `CookModeTheme.light()`
  when extension missing (test-pump safety).
- AC5: Unit test asserts both themes expose the extension and each
  token is distinct.
- AC6: No cook-mode widget is modified.
- AC7: Doc-comment records WCAG AA ratios; test asserts ≥4.5:1 on
  three text-on-surface pairs.

## File List

- `app/lib/core/theme/cook_mode_theme.dart` — NEW
- `app/lib/core/theme/app_theme.dart` — add token to both extensions
  lists
- `app/lib/core/theme/theme.dart` — barrel export
- `app/test/theme/cook_mode_theme_test.dart` — NEW

## QA Walkthrough

See `cmp-1-qa-walkthrough.md`.
