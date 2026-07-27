---
hash: imptab1
type: debug
created: 2026-07-27T18:50:00-06:00
title: Imports tab — 3 widget tests red on main; sections render 0 widgets
from: dev/dev-bqa101-2026-07-27T11:39-config-truth-qa-flip.md
status: ready
---

## Goal
`ci.yml / flutter-test` is green, so the `/devx` merge gate reflects real
breakage instead of standing red. Today it blocks every PR in the repo.

## Repro

Pre-existing on `main` — not introduced by any open PR. Identical failure
and identical counts on both:

```
# main, run 30293754580
❌ app/test/features/activity/imports_tab_test.dart: renders all four sections with one row each (failed)
❌ app/test/features/activity/imports_tab_test.dart: green row taps navigate to /recipes/:id (failed)
❌ app/test/features/activity/imports_tab_test.dart: buckets by item.status — items still render when parent job.status differs (failed)
##[error]1521 tests passed, 3 failed.

# feat/dev-bqa101 (bqa101 touches no Dart), run 30294451318 — byte-identical
##[error]1521 tests passed, 3 failed.
```

Local: `cd app && flutter test test/features/activity/imports_tab_test.dart`

## Evidence so far (not yet root-caused)

The assertions fail by finding **zero** widgets, not wrong ones:

```
Expected: exactly one matching candidate
  Actual: _TextContainingWidgetFinder:<Found 0 widgets with text containing Auto-Imported · 1: []>

Expected: exactly one matching candidate
  Actual: _TextWidgetFinder:<Found 0 widgets with text "Done": []>
```

- `imports_tab_test.dart:294,547` expect the section header text
  `Auto-Imported · 1` (label + `·` + count).
- `app/lib/features/activity/imports_tab.dart:480-482` does still pass both
  parts: `ImportStateSection(label: 'Auto-Imported', count: visibleAutoImported.length, …)`.
- So the label/count wiring looks intact at the call site — which points
  away from a copy change and toward **the section not rendering at all**
  (empty `children` because `visibleAutoImported` is empty, i.e. the test's
  fixture items aren't reaching the bucketing), rather than a renamed string.
- The third test name ("buckets by item.status — items still render when
  parent job.status differs") is consistent with that reading: the
  bucketing path is the common factor across all three failures.

Candidate commits touching this surface (unverified — none bisected yet):
`0c6bf52` (rf-5 Imports tab + activity-read-provider reactivity),
`0e643f3` (imports tab refreshes when dismiss lands elsewhere),
`f5f714c` (ffm-2 batch import-items endpoint + Flutter caller).

## Acceptance criteria
- [ ] Repro confirmed locally and the failing bucketing path identified
      (hypothesis → check → result in the status log).
- [ ] Root cause documented with file:line evidence — in particular whether
      the fixture stopped reaching `visibleAutoImported`/`visibleReview` or
      the section suppresses itself when empty.
- [ ] Fix + the 3 tests green, with `flutter test` clean overall.
- [ ] Decide whether the tests or the widget hold the correct contract —
      do not simply relax the assertions to match current behavior without
      confirming the current behavior is what users should see.

## Technical notes
- Out of scope for bqa101 (config-only change, no Dart touched). Filed from
  that story's Phase 7 after CI came back red, per the /devx rule to file
  rather than expand scope.
- The user has stated preferences for Imports-tab UX (YNAB-inspired: clear
  status icons, relative times, important-first). If sections are silently
  not rendering, that is a user-visible regression, not just test drift —
  worth checking the tab by hand before assuming it is a test-only problem.

## Status log
- 2026-07-27T18:50 — filed from /devx bqa101 Phase 7. Established
  pre-existing via identical failures on `main` (run 30293754580) and on the
  PR branch (run 30294451318). Not root-caused; evidence and the
  zero-widgets-not-wrong-widgets distinction recorded above.
