# Story cmm-3 — Sectioned step traversal + recipe-section header + navigator boundaries

**Status:** done
**Epic:** epic-cook-mode-meal
**Branch:** main

## Goal

Surface the per-component context the user needs while moving through a
sectioned cook: a small `RecipeSectionHeader` above the step card that
reads "<ComponentName> · N / M", visible only in N>1 component plans;
flat-index step traversal already wired in cmm-2; vertical-rule
boundaries on the StepNavigator pills via the
`componentBoundaries` + `componentNameForStep` params (already supported
on the widget since cmm-1 — cmm-3 just wires the meal screen to pass
them).

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | `recipe_section_header.dart` renders component name + "N / M" with `Step N of M in <ComponentName>` Semantics | ✅ Done |
| AC2 | `meal_cook_mode_screen.dart` shows header for N>1 plans; recipe cook (1-component) hides it (deferred to recipe cook screen, which uses the shared widget too via cmm-1) | ✅ Done — meal screen gates with `plan.components.length > 1` |
| AC3 | Step traversal: advancing past last step of component K → (K+1, 0); back from (K+1, 0) → (K, lastStep) | ✅ Done — flat-index navigation already from cmm-2 + verified by sectioning test |
| AC4 | StepNavigator gets `componentBoundaries`; renders 16dp wider margin + 1px rule at non-zero boundaries | ✅ Done — cmm-1 supplied the param, cmm-3 wires it |
| AC5 | Pill Semantics announce component name when boundaries are active | ✅ Done — `componentNameForStep` walks the plan |
| AC6 | Widget test: header transitions through Dressing/Salad/GrilledChicken at the right flat steps | ✅ Done |
| AC7 | Widget test: navigator boundary keys at indices 7 and 11; index 0 has no rule | ✅ Done |
| AC8 | Recipe cook (1-component) — section header NOT in tree, no boundary rules | ✅ Done — covered indirectly by cmm-1 cook_mode_test (no `RecipeSectionHeader` import in recipe cook) |
| AC9 | Flat-total progress bar — at flat-step 10 of 20 = 50% | ✅ Done — `LinearProgressIndicator.value` test asserts 10/20 |
| AC10 | Semantics tap-to-pill announces "Salad" (component name in label) | ✅ Done — semantic-label test in cmm-1 already covers the contract; reused here via `componentNameForStep` callback |

## File List

### New
- `app/lib/features/recipes/cook_mode/meal/widgets/recipe_section_header.dart`
- `app/test/meal_cook_mode_sectioning_test.dart` (3 tests)

### Modified
- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`
  - Wires `componentBoundaries` + `componentNameForStep` into StepNavigator
  - Renders `RecipeSectionHeader` above the step card for N>1 plans

## Implementation notes

- `_buildStepContent` recomputes `currentComponent` at the call site
  rather than calling `plan.stepAt(_currentStep)` again; one call per
  build keeps the hot path cheap.
- `componentNameForStep: (i) => plan.components[plan.stepAt(i).componentIndex].name`
  returns the name for any flat index; `componentBoundaries` is what
  the StepNavigator uses to decide where to draw rules. Both come
  free from `CookPlan` — no plumbing changes inside the navigator.
- `RecipeSectionHeader` uses `cookOnSurface.withAlpha(0.7)` for the
  component name and `cookAccent` for the live step number per the
  epic's design notes.
- 1-component plans are gated at the meal-screen level (`if
  (showSectionHeader)`); the recipe cook screen never imports the
  section-header widget at all.

## QA checklist

See `cmm-3-qa-walkthrough.md` for the complete walkthrough.

## Verification

- `flutter test test/meal_cook_mode_sectioning_test.dart test/meal_cook_mode_test.dart test/cook_plan_test.dart test/cook_mode_test.dart` → all green (34 tests).
- `dart analyze lib/features/recipes/cook_mode/meal/` → no warnings.
