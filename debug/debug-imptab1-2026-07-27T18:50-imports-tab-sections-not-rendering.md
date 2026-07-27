---
hash: imptab1
type: debug
created: 2026-07-27T18:50:00-06:00
title: Imports tab — 3 widget tests red on main; sections render 0 widgets
from: dev/dev-bqa101-2026-07-27T11:39-config-truth-qa-flip.md
status: done
branch: feat/debug-imptab1
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
- [x] Repro confirmed locally and the failing bucketing path identified
      (hypothesis → check → result in the status log).
- [x] Root cause documented with file:line evidence — in particular whether
      the fixture stopped reaching `visibleAutoImported`/`visibleReview` or
      the section suppresses itself when empty.
- [x] Fix + the 3 tests green, with `flutter test` clean overall.
- [x] Decide whether the tests or the widget hold the correct contract —
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
- 2026-07-27T19:05 — root-caused. NOT a code regression: the tests were
  time-bombs. Every fixture hardcoded `2026-04-18`, while
  `app/lib/features/activity/imports_tab.dart:168` applies a 30-day recency
  cutoff to the `completed` (Auto-Imported) + `skipped` buckets only —
  `awaiting_review`/`failed` are exempt as actionable (lines 165-167).
  Around 2026-05-18 the fixtures aged past the cutoff and those two sections
  stopped rendering. Hypothesis (zero widgets ⇒ section absent, not renamed)
  → check (which assertions fail) → result: all three failures are
  `completed`-bucket only (`:294` Auto-Imported, `:456` "Ship it", `:542`
  "Done"); same-dated review/failed assertions pass. None of the candidate
  commits `0c6bf52`/`0e643f3`/`f5f714c` were implicated.
- 2026-07-27T19:05 — contract call (AC #4): the WIDGET is correct. The
  cutoff is deliberate product behaviour with See-all as the documented
  escape hatch, so fixtures were anchored to `now` via `_fixtureBase`/`_at()`
  rather than relaxing any assertion. Offsets preserve the originals'
  relative ordering that the created-at-desc sort assertions rely on.
  NOT a user-visible regression — the DEBUG.md row's caveat is retired.
- 2026-07-27T19:20 — flutter test: 1524 passed, 0 failed (was 1521/3).
  CI flutter-test green (7m53s). Landed off `main` as PR #6, not on
  bqa101's branch, so the green reached all six blocked worktrees at once.
  merged via PR #6 (squash → 640987e).
