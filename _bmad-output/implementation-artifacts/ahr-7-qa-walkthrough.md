# QA Walkthrough — ahr-7 Retire Import-History Route + Regression

**Status:** complete
**Epic:** epic-activity-hub-redesign

## What to verify

### A. Legacy link redirects

- [ ] Cold-start the app with a deep-link to
      `/activity/import-history` (e.g. from a historical push
      payload). App lands on the new Activity shell with the Imports
      tab selected.
- [ ] In-app navigation to `/activity/import-history` (e.g. any stale
      in-app button) → ends on `/activity?tab=imports`.
- [ ] `/activity?filter=imports` deep-link → maps to
      `/activity?tab=imports`.
- [ ] Bottom-nav Activity tap → `/activity` (defaults to Notifications
      tab per cold-start rule).

### B. LiveImportStrip + batch_import_status_widget

- [ ] Start an import to reveal the `LiveImportStrip` on
      `AddRecipeSheet`. Tap it → lands on Imports tab of the shell
      (not on the retired screen).
- [ ] On Home, when a batch is partially done, the batch status widget
      deep-links to the shell with the Imports tab selected.

### C. Deprecation marker

- [ ] Open `app/lib/features/activity/import_history_screen.dart`.
      The class has `@Deprecated(...)` with a note pointing at
      `ImportsTab` + `/activity?tab=imports`.
- [ ] `dart analyze` on the file surfaces only the self-reference
      info-level warning (plus the pre-existing unused-import /
      unused-field warnings).

### D. Filter-chip cleanup

- [ ] No `activity_filter_chips.dart` in
      `app/lib/features/activity/widgets/`.
- [ ] No `activity_filter_chips_test.dart`.
- [ ] `ActivityTab.fromLegacyFilter` no longer exists.

### E. Existing surfaces unchanged

- [ ] Notifications tab (ahr-3 behavior) still works: swipe-archive +
      undo.
- [ ] Imports tab (ahr-4/ahr-6 behavior) still shows the four color
      sections with theme-extension colors.
- [ ] See-all footer (ahr-5 behavior) still works.

### F. Automated tests

- [ ] `flutter test test/core/router/import_history_redirect_test.dart`
      → all 4 tests pass.
- [ ] `flutter test test/features/activity/` → still green (previous
      counts preserved minus the filter-chip tests).
