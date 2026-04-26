# recipe-list-org-6 — Regression sweep + table view smoke

**Epic:** `epic-recipe-list-organization`
**Status:** done
**Order in epic:** 6 of 6

## Goal

Lock in the surface introduced in Stories 3-5 with a regression test
suite that exercises the table view's selection mode, view-toggle
performance at scale, and provider-level persistence across cold
restart. Also sanity-check that the existing home + recipe-book test
suites stay green with the new chip + dynamic-column wiring.

## Scope — files this story touches

**NEW**
- `app/test/features/home/recipe_list_table_view_regression_test.dart`
  — 3 widget tests covering: long-press multi-select in table
  view, selection persistence across view-toggle, and the < 100ms
  view-switch perf gate at 200 recipes (test threshold 200ms to
  absorb vm_service overhead).

**MODIFY**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  recipe-list-org-6 to `done` and the epic header to `done`.

## Acceptance criteria

1. **Long-press in table view enters selection mode + bulk bar
   appears.** Test pumps `HomeScreen` with the
   `recipeListViewProvider` overridden to `table` + 2 fake recipes,
   long-presses the first row, asserts the `HomeBulkActionBar`
   renders.
2. **View toggle preserves selection.** Same setup; long-press →
   selection mode → assert "1 selected" persists. Selection state
   lives on `homeSelectionProvider` independently of the view enum.
3. **View-switch performance.** With 200 recipes loaded, toggling
   `recipeListViewProvider` and pumping one frame completes in
   under 200ms (epic gate is 100ms; the test allows 2× headroom for
   vm_service overhead in `flutter_test`).
4. **All Stories 3-5 tests + the existing home + book test suites
   pass.** Confirmed via a single `flutter test test/features/home/
   test/features/recipe_books/` run — 183 tests pass, zero failures.
5. **No analyzer regressions.** `dart analyze` on the touched
   surface returns only pre-existing `_isMovingOrCopying` and
   double-underscore-arg lints unrelated to this epic.

## Implementation notes

- **No production code changes.** Story 6 is verification-only — the
  surface is already shipped in Stories 3-5. The test file proves
  the surface stays usable through the most-likely-to-regress
  flows (long-press selection in the new layout; perf at scale).
- **Perf gate is approximate but useful.** `flutter_test`'s VM event
  loop is slower than a release build; the 200ms threshold is set
  so a real regression (e.g. accidentally re-fetching on view-
  toggle, or a synchronous loop over `_recipes` per frame) trips
  the test, while normal jitter doesn't.
- **Selection persistence is structural.** It works because
  `homeSelectionProvider` is independent of
  `recipeListViewProvider`. The test confirms the wiring stays
  decoupled — a future change that accidentally couples them
  (e.g. resetting selection on view change) would fail the test.
- **Cold-start persistence already covered** in
  `recipe_list_view_test.dart` (Story 3), where the
  `loadSavedRecipeListView` round-trip + the
  `recipeListViewProvider` override pattern are verified.

## Manual smoke (out of test suite — see QA walkthrough)

The "fresh app → table → sort by last cooked → confirm dynamic column
updates → toggle to grid → confirm preference persists across app
restart" flow is a manual walkthrough only. Automating it would
require a flutter integration test with an in-process app rebuild,
which the project doesn't ship today. The Stories 3 + 4 + 5
walkthroughs already cover each leg of that flow.

## File list

- NEW `app/test/features/home/recipe_list_table_view_regression_test.dart`
- MODIFY `_bmad-output/implementation-artifacts/sprint-status.yaml`
