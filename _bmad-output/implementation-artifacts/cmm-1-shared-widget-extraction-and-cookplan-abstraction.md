# Story cmm-1 — Shared widget extraction + `CookPlan` abstraction + recipe-cook refactor

**Status:** done
**Epic:** epic-cook-mode-meal
**Branch:** main

## Goal

Move recipe-cook widget atoms (`ingredient_strip`, `step_navigator`,
`step_timers_row`, `manual_timer_sheet`, `timer_completion_overlay`,
`post_cook_feedback_sheet`) and util files (`timer_regex`,
`cook_timer_token`) into `shared/`, plus extract the inline
`_buildActiveTimers` helper out of `cook_mode_screen.dart` into a new
`shared/widgets/active_timers_row.dart` widget. Define the `CookPlan`
abstraction (`CookPlan.fromRecipe` + `CookPlan.fromMeal`) that both
recipe cook and meal cook (cmm-2..cmm-7) consume. Refactor
`cook_mode_screen.dart` to drive every state-mutating handler off the
plan instead of the legacy ad-hoc `_steps` / `_ingredients` lists.
Extend `IngredientStrip` with optional `sourceTagBuilder` and
`StepNavigator` with optional `componentBoundaries` /
`componentNameForStep` / `doneLabel` so meal cook can render section
boundaries + per-chip source tags + a "Finish meal" primary button
without a fork.

## Acceptance Criteria — status

| AC  | Description | Status |
|-----|-------------|--------|
| AC1 | `shared/widgets/` directory contains all moved widget files | ✅ Done |
| AC2 | External consumers' imports updated to `shared/widgets/...` | ✅ Done — calendar_screen + 7 test files updated |
| AC3 | `cook_plan.dart` defines `CookPlan` / `CookComponent` / `CombinedIngredient` with both factories + `loadFailed` defaults to false | ✅ Done |
| AC4 | `cook_mode_screen.dart` consumes `CookPlan.fromRecipe`, internal "Step N of M" subtitle removed | ✅ Done |
| AC5 | Every existing cook-mode test passes with no behavioural change | ✅ Done — 1211 tests green |
| AC6 | `cook_plan_test.dart` covers boundary indexing, out-of-range throws, `loadFailed`, `stableKey` | ✅ Done — 13 unit tests passing |
| AC7 | `IngredientStrip` `sourceTagBuilder` renders per-chip tag chip + "--- From X ---" group dividers in expanded view | ✅ Done — 2 widget tests |
| AC8 | `StepNavigator` `componentBoundaries` adds 16dp wider margin + 1px vertical rule + Semantics with component name | ✅ Done — 3 widget tests (boundary keys, length-1 no-op, semantics) |
| AC9 | `PostCookFeedbackSheet` accepts `List<ComponentRatable>`; single-element list pixel-identical to today | ✅ Done — existing `post_cook_feedback_test.dart` passes unchanged |
| AC10 | `cook_mode/widgets/` only contains non-shared widgets (cook_reset_confirm_sheet + cook_resume_gate_sheet); `tools/no-cook-chat-check.sh` green | ✅ Done — `no-cook-chat-check: OK` |
| AC11 | `flutter test` green; `dart analyze` clean (no new issues from the refactor) | ✅ Done |

## File List

### Moved (with `git mv`, history preserved)
- `app/lib/features/recipes/cook_mode/widgets/ingredient_strip.dart` → `shared/widgets/ingredient_strip.dart`
- `app/lib/features/recipes/cook_mode/widgets/step_navigator.dart` → `shared/widgets/step_navigator.dart`
- `app/lib/features/recipes/cook_mode/widgets/step_timers_row.dart` → `shared/widgets/step_timers_row.dart`
- `app/lib/features/recipes/cook_mode/widgets/manual_timer_sheet.dart` → `shared/widgets/manual_timer_sheet.dart`
- `app/lib/features/recipes/cook_mode/widgets/timer_completion_overlay.dart` → `shared/widgets/timer_completion_overlay.dart`
- `app/lib/features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart` → `shared/widgets/post_cook_feedback_sheet.dart`
- `app/lib/features/recipes/cook_mode/util/timer_regex.dart` → `shared/util/timer_regex.dart`
- `app/lib/features/recipes/cook_mode/util/cook_timer_token.dart` → `shared/util/cook_timer_token.dart`

### New
- `app/lib/features/recipes/cook_mode/shared/cook_plan.dart` — `CookPlan` / `CookComponent` / `CookStep` / `CombinedIngredient` / `ComponentRatable`
- `app/lib/features/recipes/cook_mode/shared/widgets/active_timers_row.dart` — extracted from inline `_buildActiveTimers`
- `app/test/cook_plan_test.dart` — 13 unit tests for plan factories + indexing

### Modified
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` — consumes `CookPlan.fromRecipe`; uses `ActiveTimersRow`; uses new `PostCookFeedbackSheet(components: [...])` constructor; removes `_StepData` (replaced by `CookStep`); drops "Step N of M" subtitle from the step card
- `app/lib/features/recipes/cook_mode/shared/widgets/ingredient_strip.dart` — `sourceTagBuilder` parameter; per-chip tag rendering in compact view; group dividers in expanded view
- `app/lib/features/recipes/cook_mode/shared/widgets/step_navigator.dart` — `componentBoundaries` + `componentNameForStep` + `doneLabel` parameters; vertical rule before non-zero boundary indices
- `app/lib/features/recipes/cook_mode/shared/widgets/post_cook_feedback_sheet.dart` — accepts `List<ComponentRatable>`; single-component path renders pixel-identically; multi-component path stubbed for cmm-6
- `app/lib/features/calendar/calendar_screen.dart` — passes new `components: [ComponentRatable(...)]` constructor
- `app/test/cook_mode_test.dart` — adds 5 new test cases (source-tag rendering, group dividers, boundary keys, length-1 no-op, semantics)
- `app/test/post_cook_feedback_test.dart` — updated to new constructor signature
- `app/test/cook_mode_gesture_test.dart` / `cook_mode_test.dart` / `cook_mode_timers_integration_test.dart` / `manual_timer_sheet_test.dart` / `step_timers_row_test.dart` / `timer_regex_test.dart` / `features/recipes/cook_mode/timer_completion_overlay_test.dart` — import-path updates

## Implementation notes

- `IngredientStrip` chip width is now `72dp` when a source tag is
  present (vs `64dp` without) and the name `maxLines` drops to 1, to fit
  the tag chip inside the 80dp horizontal strip without overflow.
- `StepNavigator` skips drawing a vertical rule before the index-0
  pill, even when `componentBoundaries.contains(0)` (always true for
  meal cook). The first pill never has a "before" rule.
- `CookPlan.fromMeal` accepts `List<Map<String, dynamic>?>` so cmm-2 can
  pass `null` for components whose recipe fetch failed; the plan
  constructor flips `loadFailed: true` for those entries instead of
  throwing.
- `cook_mode/widgets/` retains `cook_reset_confirm_sheet.dart` and
  `cook_resume_gate_sheet.dart` (cmm-7 will share these from the same
  location; no need to move them in cmm-1).

## QA checklist

See `cmm-1-qa-walkthrough.md` for the complete walkthrough.

## Verification

- `flutter test` → 1211/1211 passing.
- `dart analyze lib/features/recipes/cook_mode/ lib/features/calendar/calendar_screen.dart` → 3 pre-existing warnings, zero new issues.
- `bash tools/no-cook-chat-check.sh` → `no-cook-chat-check: OK`.
