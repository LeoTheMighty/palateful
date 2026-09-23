---
hash: perfflake1
type: debug
created: 2026-09-22T14:30:00-06:00
title: The 200ms grid↔table perf assertion fails under parallel load, not under regression
from: dev/dev-fxfuse-2026-09-20T10:35-drain-the-fixture-date-fuse-baseline.md
status: ready
owner: null
branch: null
---

## Goal

`switching grid ↔ table on 200 recipes stays under 200ms`
(`app/test/features/home/recipe_list_table_view_regression_test.dart:232`)
should fail when the view-switch gets slower, and only then. Today it also
fails when the machine is busy, which makes a red `flutter-test` ambiguous
in exactly the way this repo can least afford — `flutter-test` is the root
job every deploy job hangs off.

## Reproduction / evidence (observed 2026-09-22 during fxfuse)

Same tree, same commit, three observations:

1. Full suite, machine otherwise idle → **1642 passed, 0 failed**.
2. Full suite, machine running two other Flutter suites concurrently →
   **1641 passed, 1 failed**, the failure being this assertion.
3. The file alone, immediately after (2), three consecutive runs →
   **3/3 green**.

The measured region (`:250-256`) wraps only
`recipeListViewProvider.notifier.toggle()` plus one `pump()`; the 200-item
fixture construction happens before the stopwatch starts, so fixture cost
is not the variable. What varies is CPU contention.

## Acceptance criteria

- [ ] A busy machine cannot turn this assertion red on its own. Options,
      in rough order of preference: measure work rather than wall-clock
      (frame/build counts, or `tester.binding` elapsed frame time); keep
      the wall-clock assertion but make it a warning outside CI; or pin
      the budget to a calibration measurement taken in the same process so
      the threshold scales with the host.
- [ ] Whatever replaces it still fails on a genuine regression — prove it
      the way fxfuse proved its time-travel check: deliberately slow the
      toggle, watch the assertion go red, record the recipe in the test's
      header.
- [ ] The 100ms product gate from Story 6 stays documented wherever the
      assertion ends up; that number is a real commitment, not an artifact
      of the test harness.

## Technical notes

- Current threshold is 200ms against a documented 100ms product gate, with
  the extra 100ms explicitly justified as vm_service overhead
  (`:258-261`). That headroom is already absorbing host variance; under
  three concurrent suites it is not enough.
- This is pre-existing — fxfuse only touched the file's fixture dates
  (`created_at` / `updated_at` anchored to `_at(0)`), all outside the timed
  region. It is filed rather than fixed because changing a perf assertion's
  shape is a product judgment about what the gate protects, not a test-fixture
  cleanup.
- Related: the same file is the only home-surface test that renders the
  table view's dynamic column, so it is load-bearing beyond this one
  assertion. Don't delete the test to make the flake go away.

## Status log
- 2026-09-22 — filed from `/devx fxfuse` phase 5 after the assertion failed
  once in a loaded full-suite run and passed 3/3 standalone on the same tree
  minutes later.
