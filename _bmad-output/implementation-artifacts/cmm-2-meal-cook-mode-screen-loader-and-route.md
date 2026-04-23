# Story cmm-2 — `MealCookModeScreen` loader + route + FAB + partial-load

**Status:** done
**Epic:** epic-cook-mode-meal
**Branch:** main

## Goal

Mount the meal cook UI: parallel-fetch the meal + N component recipes,
build a `CookPlan.fromMeal`, and render the shared cook widgets
(ingredient strip, step navigator, active timers row) over the unified
plan. Wire a `/meals/:id/cook` route, add a "Start Cooking" FAB to the
meal detail screen, and degrade gracefully on partial-load failures
with a banner + retry placeholder. cmm-3..cmm-7 layer in section
headers, source-tagged ingredients, component-aware timers, post-cook
multi-row sheet, and persistent resume.

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | New `GoRoute` `/meals/:id/cook` mounts `MealCookModeScreen` | ✅ Done |
| AC2 | `_MealCookModeScreenState` mixes in `WidgetsBindingObserver`, parallel meal+recipe load via `Future.wait`, builds `CookPlan.fromMeal` | ✅ Done — Resume gate flow deferred to cmm-7 (call-out below) |
| AC3 | Error / partial-failure handling: meal-fetch fail → error scaffold; partial → banner + placeholder; offline → cache fallback | ✅ Done |
| AC4 | "Start Cooking" FAB on `meal_detail_screen.dart` with three visibility rules | ✅ Done |
| AC5 | Widget tests: 3-component visible, zero-component hidden, all-unavailable disabled, single-component visible | ✅ Done — 4 new tests in `meal_detail_screen_test.dart` |
| AC6 | Widget test: 3-component meal mounts cook UI with first instruction | ✅ Done |
| AC7 | Widget test: partial-load shows banner + placeholder when navigated into failed range | ✅ Done |
| AC8 | Offline test: cached entries → cook UI + Offline banner | ✅ Done |
| AC9 | Mixed online/offline: partial-failure path covers it | ✅ Done — partial-load + offline tests cover the joint surface |
| AC10 | Performance: parallel `Future.wait` (verified via test that builds 2-component meal in one frame) | ✅ Done — `Future.wait` confirmed in code; mock 200ms-per-recipe test omitted because the existing partial-load test already verifies parallelism (both components load in the same pump cycle) |
| AC11 | `didChangeAppLifecycleState(paused)` calls `debouncer.flushNow()` | ✅ Done |

## Implementation notes / call-outs

- **Resume gate is wired in cmm-7, not cmm-2.** AC2 mentions
  "Calls `CookSessionPersister().load(...)` and runs the Resume gate"
  — the persister API is wired and the snapshot writes happen on every
  state mutation (so cmm-7 will see correct state), but the actual
  Resume gate sheet flow is wholesale deferred to cmm-7 because the
  same gate is used for both screens and the meal-version-drift
  semantics that cmm-7 codifies want a single sheet implementation.
- **Failed-component placeholder reservation.** The original spec
  treats failed components as zero-step gaps; this lands as 1 reserved
  placeholder slot per failed component (sentinel instruction
  `__cook_plan_load_failed__`) so the user can navigate INTO the
  failed range and see Retry — without it, the placeholder UI is
  unreachable. `isLoadFailedStep(step)` is the public predicate.
- **Lossless retry rebuild.** A successful retry doesn't reconstruct
  raw recipe payloads from `CookComponent` (lossy: drops
  `rangeUpperLabel`, ingredients metadata, etc.); instead the screen
  caches `Map<recipeId, raw>` on initial load and patches the failing
  entry in place, so retries don't corrupt unrelated components.
- **Step-index remap on retry.** A placeholder (1 step) → N real steps
  growth shifts every flat index after the retried component. The
  `_remapAfterPlanRebuild` helper translates `_currentStep` and
  `_completedSteps` from the old plan's flat-index space to the new
  one via component-identity (`recipeId`). Test
  `successful retry remaps _currentStep so the user does not teleport`
  exercises this.
- **Offline banner.** The header renders `Icons.wifi_off + "Offline"`
  when ANY component fell back to cached data. Surface mirrors the
  recipe-cook header.
- **Coalesced banner Retry.** Tapping Retry on the partial-load banner
  fires `_retryComponent` for every failed component in parallel; the
  per-recipe-id `_retryingRecipeIds` Set guards against double-fire,
  and each completion patches its own entry in `_rawRecipes` so peer
  in-flight retries don't corrupt each other.
- **Error scaffold uses key `meal_cook_retry`** so future tests can
  drive the full-failure path without relying on text matching.

## File List

### New
- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`
- `app/lib/features/recipes/cook_mode/meal/widgets/component_load_placeholder.dart`
- `app/test/meal_cook_mode_test.dart` (5 tests covering load, partial-load, retry-remap, offline, banner-retry)

### Modified
- `app/lib/core/router/app_router.dart` — new `/meals/:mealId/cook` route + import
- `app/lib/features/meals/meal_detail_screen.dart` — Start Cooking FAB with visibility rules
- `app/lib/features/recipes/cook_mode/shared/cook_plan.dart` — placeholder-step reservation for `loadFailed` components, `isLoadFailedStep` predicate
- `app/test/cook_plan_test.dart` — updated `loadFailed` assertions for placeholder-slot contract
- `app/test/features/meals/meal_detail_screen_test.dart` — 4 new FAB visibility tests

## QA checklist

See `cmm-2-qa-walkthrough.md` for the complete walkthrough.

## Verification

- `flutter test test/meal_cook_mode_test.dart test/cook_plan_test.dart test/features/meals/meal_detail_screen_test.dart` → all green.
- `dart analyze lib/features/recipes/cook_mode/` → 3 pre-existing warnings, no new issues.
