# QA Walkthrough — ahr-6 ImportStateColors Theme Extension

**Status:** complete
**Epic:** epic-activity-hub-redesign

## What to verify

### A. Colors identical to pre-ahr-6 state

- [ ] Open Imports tab. Section chips + row chips render with the
      same colors as before (blue/yellow/red/green).
- [ ] Switch to dark mode. Chips render dark-palette colors.
- [ ] No visual regression in `LiveImportStrip` (progress glyph +
      chevron should still be blue/primary).
- [ ] `ImportActivityDetail`'s Stage chip shows the same state-to-
      color mapping (review=yellow, failed=red, etc.).

### B. Token legibility sanity

- [ ] Run `flutter test test/theme/import_state_colors_test.dart` —
      all three tests pass.
- [ ] In app, at small 14px/700 chip text: every state is distinguishable
      from its tinted background in both themes.

### C. No refs to raw `colorScheme` for state colors

- [ ] `grep -n "colorScheme.primary\|colorScheme.tertiary\|colorScheme.error\|colorScheme.secondary"
      app/lib/features/activity/` returns only non-import-state refs
      (e.g., chip backgrounds on the snackbar, outline colors).
