---
hash: imptb1
type: debug
created: 2026-07-27T18:53:00-06:00
title: imports_tab_test.dart — 3 widget tests red on main
from: btri01
status: ready
owner:
branch:
---

## Goal
`flutter test` on `main` is not green: three widget tests in
`app/test/features/activity/imports_tab_test.dart` fail. Find out whether the
tests or the Imports tab drifted, and make the suite green again.

## Reproduction

```bash
cd app && flutter test test/features/activity/imports_tab_test.dart
```

Result on `main` (746bbbe) and on `feat/debug-btri01` alike — 5 passed, 3
failed. Confirmed independent of any btri01 change by stashing the branch's
only `app/lib` edit and re-running: same three failures.

| Test | Failure |
|---|---|
| `renders all four sections with one row each` (line 294) | `Found 0 widgets with text containing "Auto-Imported · 1"` — expected exactly one |
| `green row taps navigate to /recipes/:id` | `tap()` on `find.text('Ship it')` found 0 widgets |
| `buckets by item.status — items still render when parent job.status differs` (line 542) | same shape — expected row text absent |

All three are "the row I expected to render isn't there", which points at one
cause: either the section header / row copy changed (`Auto-Imported · N`), or
the bucketing that decides which rows land in which section changed, and the
test's fixtures no longer land where it looks for them.

## Acceptance criteria
- [ ] Root cause identified: test drift vs. a real Imports-tab regression —
      say which, with the commit that introduced it
- [ ] `flutter test test/features/activity/imports_tab_test.dart` green
- [ ] `flutter test` (whole app) green, or any *other* remaining failure
      filed separately
- [ ] If it was a real regression, the user-visible symptom is described
      (which rows stopped rendering, in which section)

## Technical notes
- Prime suspect list: anything that touched Imports-tab bucketing or section
  copy after the test was written. `git log --oneline -- app/lib/features/activity/imports_tab.dart`
  is the first stop.
- Note bas-2 renamed "Archive" → "Dismiss" across this exact surface. If the
  copy assertions drifted once already, they may have drifted again.
- The non-failing noise in the same run (`API Error: 400 …` from
  `non-blue swipe archives + fires API`) is an intentional error-path fixture,
  not a failure — don't chase it.

## Status log
- 2026-07-27T18:53 — filed by btri01 after a full-suite run during shopping-cart
  triage: 1530 passed, 3 failed, all three in this file, all pre-existing on main
