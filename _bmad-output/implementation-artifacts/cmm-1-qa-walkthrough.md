# cmm-1 — QA walkthrough

Recipe-cook UX must be visually and behaviourally **identical** to
pre-refactor. Meal cook is wired in cmm-2; this story is the prep step.

## Setup
- Build the app from `main` (current commit). No new env vars.
- Sign in with any user. At least one recipe with steps required.

## Smoke 1 — Recipe cook still works end-to-end (~3 min)
1. Open any recipe with at least 3 steps.
2. Tap "Start Cooking" FAB.
3. Cook UI mounts. Header shows recipe name.
4. **Verify the step card no longer shows the big "1 of 3" subtitle**
   inside the card body — only the progress bar + step text.
5. Swipe to step 2. Progress bar advances ~33% → ~66%.
6. Tap an ingredient chip — turns checked, no source-tag chip visible.
7. Expand the ingredient strip — no "--- From ... ---" dividers visible
   (single-component plan).
8. Start a manual 1-min timer from the timer header icon.
   - Active timer chip appears in the row above the ingredient strip.
   - Same shape, color, fonts, ring-progress as before.
9. Tap the chip → timer detail sheet (Cancel / Restart) opens.
10. Cancel the timer; chip disappears.
11. Tap "Done" on the last step → post-cook feedback sheet opens.
12. **Verify single-row layout pixel-identical** to pre-refactor: drag
    handle, "How did it go?" header, recipe name, 5 stars, notes field,
    Save / Skip.
13. Tap 4 stars → tap Save → sheet closes, returns to recipe detail.

## Smoke 2 — Resume gate still triggers (~2 min)
1. Open a recipe, start cooking, advance to step 2, start a 5-min timer.
2. Force-quit the app.
3. Re-open and navigate back to that recipe → tap Start Cooking.
4. Resume / Start Over gate sheet appears with the same copy as before.
5. Tap Resume → mounts at step 2 with the timer still ticking.
6. Tap overflow → Reset cook → confirm. Cook session reset.

## Smoke 3 — Calendar "Mark cooked" still works (~1 min)
1. From a meal-event tile in the calendar, tap "Mark cooked" on a
   per-recipe event.
2. Post-cook feedback sheet opens — same as today.
3. Rate it, save. Should not throw.

## Negative
- No "--- From ... ---" dividers visible anywhere in recipe cook mode.
- No source-tag chip visible on any ingredient chip in recipe cook mode.
- Step navigator pills have no vertical rules between them.

## Automated coverage
- `flutter test test/cook_plan_test.dart` — 13 tests pass.
- `flutter test test/cook_mode_test.dart` — 11 tests pass (including 5
  new tests for source tags + boundaries + Semantics).
- `flutter test test/post_cook_feedback_test.dart` — pass with new
  constructor signature.
- `flutter test test/cook_mode_resume_test.dart` — pass.
- `bash tools/no-cook-chat-check.sh` — green on the expanded tree.

## Sign-off
Story is shippable when all 3 smokes above show no regression and the
automated suites listed above are green.
