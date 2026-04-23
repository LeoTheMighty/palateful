# Story cmm-4 — Interlaced combined ingredient strip with source tags

**Status:** done
**Epic:** epic-cook-mode-meal
**Branch:** main

## Goal

Render the meal's combined ingredient list (one row per recipe-ingredient,
no dedup) at the top of the cook UI, each chip tagged with its source
component name. Compact strip carries a per-chip tag chip
(10-grapheme truncated); expanded grid view groups by source component
with `--- From <ComponentName> ---` dividers. Check-off state is keyed
by stable `componentIndex:orderIndex` so re-imported recipes don't
silently reset checks. The Resume-side "Ingredients changed" snackbar
fires from cmm-7's restoration flow; cmm-4 lays the stable-key
plumbing it depends on.

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | `CookPlan.fromMeal` builds flat tagged ingredient list (cmm-1) | ✅ Done in cmm-1; verified by parity test |
| AC2 | Strip rendered with `sourceTagBuilder`; per-chip tag (compact) + group divider (expanded) | ✅ Done — wired in `meal_cook_mode_screen.dart` |
| AC3 | Stable key `<componentIndex>:<orderIndex>` + restoration drift | ✅ Done — `_checkedIngredientKeys` set + `_checkedFlatIndices` getter silently drops missing keys |
| AC4 | No dedup — 2× "1 cup flour" → 2 chips | ✅ Done — covered by `no dedup` plan test |
| AC5 | Widget tests: total count, per-chip tags compact, group dividers expanded, dedup-NOT-applied, 10-char truncation | ✅ Done — 4 widget tests in `meal_cook_mode_ingredients_test.dart` |
| AC6 | 1-component plan: no source tags, no dividers (recipe-cook compat) | ✅ Done — plain `IngredientStrip` (no builder) |
| AC7 | Parity with backend `aggregate_meal_ingredients(meal)` shape | ✅ Done — flat-iteration contract test (component order, then ingredient order) |
| AC8 | Order-drift: stable-key set rebinds; missing keys silently dropped (snackbar fires from cmm-7) | ✅ Done — drift test: `1:1` orphan → empty checked set on rebuild |

## File List

### New
- `app/test/meal_cook_mode_ingredients_test.dart` (9 tests)

### Modified
- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`
  - Wires `sourceTagBuilder` into `IngredientStrip` for N>1 plans
  - Builder reads `plan.ingredients[i].sourceComponentName` (already
    populated by `CookPlan.fromMeal` since cmm-1)

## Implementation notes

- The 10-character grapheme truncation lives in
  `_IngredientChip._truncatedTag` (already added in cmm-1's review
  fix loop using `package:characters`). Truncation handles emoji and
  combining marks safely.
- Single-component (recipe cook) gets `null` builder, leaving
  rendering pixel-identical to pre-meal cook.
- Stable-key check-state is a `Set<String>`. The flat-index Set
  `_checkedFlatIndices` is derived per-build via the getter; this
  costs O(N) per render but N is small (typical meal is <30
  ingredients).
- The Resume-side "Ingredients changed since your last session"
  snackbar fires when cmm-7 restores a persisted state — the
  one-shot UX is part of cmm-7 AC4 because it requires the resume
  gate flow that cmm-7 ships.

## QA checklist

See `cmm-4-qa-walkthrough.md`.

## Verification

- `flutter test test/meal_cook_mode_ingredients_test.dart` — 9 tests.
- `flutter test test/meal_cook_mode_test.dart test/meal_cook_mode_sectioning_test.dart test/cook_plan_test.dart test/cook_mode_test.dart` — all 43 green.
- `dart analyze lib/features/recipes/cook_mode/` — 3 pre-existing warnings, no new.
