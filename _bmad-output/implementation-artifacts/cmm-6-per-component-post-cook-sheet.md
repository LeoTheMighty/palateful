# Story cmm-6 — Per-component post-cook sheet + N writes + early finish

**Status:** done
**Epic:** epic-cook-mode-meal
**Branch:** main

## Goal

Replace the cmm-1 stub of `PostCookFeedbackSheet` for `length > 1`
with a full multi-row layout: one rating row per started component,
scrollable when many rows overflow the viewport, sequential `POST
/v1/cooking-logs` writes per `rating > 0`, `CookingLogCreated`
mutation events for each successful POST, partial-failure snackbar
"Cooked X of Y components logged", and persister-clear on submission
regardless of partial-failure outcome. Add the "Finish cooking now"
overflow item with a confirmation that opens the sheet pre-seeded
with only the components the user actually entered.

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | "Finish meal" Done button appears on the final flat-step | ✅ Done — StepNavigator already supports `doneLabel`; default "Done" is appropriate; final step → `_finishCooking` |
| AC2a | Overflow "Finish cooking now" + destructive-right confirm; sheet seeded with started components | ✅ Done |
| AC2 | Multi-row sheet with scrollable ListView; sequential POSTs per `rating > 0`; CookingLogCreated emitted | ✅ Done |
| AC3 | Persister cleared even on partial failure (user already submitted) | ✅ Done |
| AC4 | All-zeroes Done allowed: 0 POSTs, "Meal finished" snackbar, persister cleared | ✅ Done |
| AC5 | Widget tests: 3-row mount, 5/4/0 → 2 POSTs + 2 events, partial-failure snackbar, all-zeroes path, scroll for many rows, early-finish 2-row seed | ✅ Done — 6 tests in `meal_post_cook_feedback_test.dart`. Early-finish row-count is exercised at the unit level; the screen-level wiring is covered by smoke testing |
| AC6 | Recipe cook (1-component) — single-row layout pixel-identical, existing tests pass unchanged | ✅ Done — `post_cook_feedback_test.dart` 9/9 green |
| AC7 | Semantics: each row announces "<Component>, rate N of 5 stars" + "Notes for <Component>" | ✅ Done — `Semantics` wrappers in `_buildMultiRow` |
| AC8 | Cancel on early-finish confirmation leaves cook UI intact | ✅ Done — `showModalBottomSheet` returns null/false; no state mutation |

## File List

### New
- `app/test/meal_post_cook_feedback_test.dart` (6 tests)

### Modified
- `app/lib/features/recipes/cook_mode/shared/widgets/post_cook_feedback_sheet.dart`
  - Removed cmm-1 `UnimplementedError` stub
  - New `_multiRatings` / `_multiNotes` per-row state
  - `_buildMulti` renders N rating rows in a `ListView.separated`
    with per-row Semantics, scrollable when overflow
  - `_saveMulti` does sequential POSTs, emits `CookingLogCreated`,
    surfaces a "Cooked X of Y" snackbar on partial failure, fires
    `onComplete(saved: true)` even on partial failure / all-zero
- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`
  - `_finishCooking` opens the multi-row sheet via
    `_openPostCookSheet`
  - New `_finishCookingEarly` for the overflow "Finish cooking now"
    flow (confirmation sheet → sheet seeded with components reached)
  - Overflow menu adds `finish_now` item alongside `reset`

## Implementation notes

- The PostCookFeedbackSheet sits on `MutationBus` via the top-level
  `emitMutation()` helper. The full Riverpod listener tree
  (`mutationBusProvider`) is hot regardless of who called emit; the
  sheet doesn't need a `Ref`.
- `cookedAt` is normalized to UTC ISO-8601 before being submitted —
  matches the backend `CookingLogCreate.cooked_at` field shape.
- Offline path mirrors the single-recipe flow: writes to
  `RecipeCacheService.logCook` and skips the mutation event because
  the providers expect the wire payload.
- Early-finish seeding uses `_currentStep >= flatIndexFor(ci, 0)` to
  decide which components the user "reached." A user who confirms
  early-finish before tapping Next at all gets `ratables.empty` →
  the persister clears and the screen pops without sheet — matching
  the AC's "all uncooked components are omitted" intent.
- The destructive-right-side button on the early-finish confirm
  uses `colorScheme.error` per the locked design rule from
  `epic-cook-mode-resume`.

## QA checklist

See `cmm-6-qa-walkthrough.md`.

## Verification

- `flutter test test/meal_post_cook_feedback_test.dart` — 6 tests.
- `flutter test test/post_cook_feedback_test.dart` — 9 tests
  (single-component regression).
- Full app suite — 1243 / 1243 passing.
- `dart analyze lib/features/recipes/cook_mode/` — 3 pre-existing
  warnings, no new.
