# cmp-2 — Migrate cook_mode_screen.dart to CookModeTheme

**Status:** review
**Epic:** epic-cook-mode-polish

## Summary

- Removed `Theme(data: AppTheme.dark(), …)` wrapping around the entire
  `build()` method. Cook mode now inherits the ambient app theme.
- Every `colorScheme.primary` / `colorScheme.tertiary` / `colorScheme.
  surfaceContainerLow` reference in the file now resolves through
  `CookModeTheme` tokens.
- Deleted the completed-state branch inside `_buildStepContent` — the
  current step never renders with line-through, dim alpha, check icon,
  or completed border. Completed visuals now live exclusively in
  StepNavigator pills (migrated in cmp-3). This is the critical UX fix
  for the dogfood regression where stepping back still showed the
  walked-past step as "completed".
- Loading scaffold + error scaffold + header + active-timer pill + post-
  cook feedback sheet + timer-detail sheet + snackbar all use tokens.
- Offline indicator uses `cookOffline` (calm warm brown / hazelnut) in
  place of raw `colorScheme.tertiary`.

## Acceptance criteria

All ACs in epic cmp-2 satisfied. Completed-step untoggle-on-back is
wired as part of cmp-4 (logic-only, same file).

## File list

- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` — modified

## QA walkthrough

See `cmp-2-qa-walkthrough.md`.
