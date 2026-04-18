# Story ahr-6: Flutter — `ImportStateColors` theme extension + audit

**Status:** done
**Epic:** epic-activity-hub-redesign
**Depends on:** ahr-4 (ImportsTab already uses the color slots
inline)

## Goal
Centralize the four import-state colors behind a single `ImportStateColors`
theme extension so a future color tuning lands in one place. Audit
existing import-related code to route through the extension instead of
bare `colorScheme.X` refs.

## Scope (from epic)

- **`ImportStateColors`** extends `ThemeExtension<ImportStateColors>`
  with `inProgress` / `needsReview` / `failed` / `autoImported`. Token
  names are locked — no renames, no new variants like `dismissed` /
  `archived` (those are states, not colors).
- **Wired into light + dark ThemeData** via the existing
  `extensions: const <ThemeExtension>[...]` pattern on both
  `AppTheme.light()` and `AppTheme.dark()`.
- **Colors map today to the same `colorScheme` slots ahr-4 uses:**
  - light: `chocolate` (primary) / `terracotta` (tertiary) /
    `error` (red) / `hazelnut` (secondary).
  - dark: `terracotta` (primary) / `terracotta` (tertiary) /
    `coral` (error) / `hazelnutLight` (secondary).
  These are the same values hardcoded in ahr-4's
  `ImportsTab.build()`; we just route them through the extension.

- **Audit**: migrate every import-related reference to the extension.
  Files touched by the audit:
  - `app/lib/features/activity/imports_tab.dart` — the four section
    color args are fed from the extension; removes the one place
    hardcoded choices exist.
  - `app/lib/features/activity/widgets/import_row.dart` — if a caller
    doesn't explicitly pass `stateColor`, we fall back to the
    extension's color matching the chip label (low-priority follow-
    on: tighter typed API).
  - `app/lib/features/activity/widgets/import_state_section.dart` —
    no change (color is already passed in).
  - `app/lib/features/activity/widgets/import_activity_detail.dart` —
    state chip in `_buildStageRow` uses `_statusColor` mapping that
    today reads raw `colorScheme` slots. Route through the extension.
  - `app/lib/features/recipes/add_recipe/widgets/live_import_strip.dart`
    — uses blue for the progress glyph. Route through the extension.

- **Non-import color references stay on `colorScheme`.** Only the
  four state tokens migrate — general theme colors, buttons, text
  don't change.

- **WCAG AA contrast**: widget test asserts that chip text over the
  chip background (tinted at alpha 0.15 per ahr-4's `_StateChip` and
  `ImportStateSection`) passes ≥ 4.5:1 in both brightnesses. We
  implement the contrast check via a small utility rather than
  pulling in a new dependency.

## Contract decisions

- **Tinted background uses `withValues(alpha: 0.15)` applied in the
  widget**, not in the extension. The extension exposes the raw
  color; widgets decide the tint. This keeps the extension a simple
  data bag.

- **Contrast is asserted between the raw token color and the
  surface** it renders over — matching how Flutter computes
  Foreground/Background for chip text. The tinted 0.15 background
  over `colorScheme.surface` composites to a near-surface color;
  the foreground is the raw token; so the ratio between the token
  and `surface` is the operative one.

- **Fallback when extension is missing**: `Theme.of(context).extension<ImportStateColors>()`
  returns nullable; widgets fall back to `colorScheme` slots verbatim
  so unit tests without a full theme stack still render.

- **No migration of `ImportHistoryScreen`'s legacy color refs** —
  that file is retired in ahr-7 (gets `@Deprecated`); touching it now
  cascades deprecation warnings.

## Acceptance Criteria mapping

1. ✅ Four fields, names locked.
2. ✅ Wired into light + dark `ThemeData.extensions`.
3. ✅ WCAG AA contrast test.
4. ✅ Audit + migration across `app/lib/features/activity/` and
   `app/lib/features/recipes/add_recipe/`.
5. ✅ Non-import refs stay on `colorScheme`.
6. ✅ `ImportActivityDetail`, `LiveImportStrip`, `ImportStateSection`,
   `ImportRow` all read from the extension.
7. ✅ Widget test for the extension resolution.

## File List

- `app/lib/core/theme/import_state_colors.dart` — new (extension +
  light/dark instances + convenience context getter)
- `app/lib/core/theme/theme.dart` — modified (export the new file)
- `app/lib/core/theme/app_theme.dart` — modified (register the
  extension on light + dark ThemeData)
- `app/lib/features/activity/imports_tab.dart` — modified (use
  extension instead of raw `colorScheme.primary/tertiary/error/secondary`)
- `app/lib/features/activity/widgets/import_activity_detail.dart` —
  modified (migrate `_statusColor`)
- `app/lib/features/recipes/add_recipe/widgets/live_import_strip.dart`
  — modified (migrate blue/progress glyph)
- `app/test/theme/import_state_colors_test.dart` — new
