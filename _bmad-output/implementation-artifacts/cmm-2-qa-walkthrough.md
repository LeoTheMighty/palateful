# cmm-2 — QA walkthrough

This story ships the `/meals/:id/cook` route, the Start Cooking FAB on
meal detail, and the partial-load degrade. Section header (cmm-3),
combined ingredient strip with source tags (cmm-4), component-aware
timers (cmm-5), multi-row post-cook sheet (cmm-6), and persistent
resume (cmm-7) are NOT in this story — verify only what's in scope.

## Setup
- Build the app from `main` (current commit). No new env vars.
- Sign in. Need at least one meal with 2+ component recipes.

## Smoke 1 — FAB visibility on meal detail (~2 min)
1. Open a meal with 2 recipes, both available → bottom-right FAB
   "Start Cooking" visible + enabled.
2. Open the meal-edit screen → swipe-remove all components down to
   zero. Save. → FAB hidden.
3. Re-add a component → FAB visible + enabled.
4. Archive every component recipe (or use a meal where all components
   are unavailable) → FAB visible but disabled with tooltip
   "Add a recipe to start cooking".

## Smoke 2 — Cook flow happy path (~3 min)
1. From a meal with 3 components (e.g., Dressing + Salad + Main), tap
   the FAB → cook UI mounts within ~1s on Wi-Fi.
2. Header shows the meal name + manual-timer icon + cooking-time +
   close + overflow.
3. Step card shows the FIRST step's instruction (currently labelled
   `Step 1 of <Component Name>` text from the test fixture; in real
   recipes this is the recipe's first step instruction).
4. Tap Next twice → step counter advances (no section header yet —
   that's cmm-3).
5. Tap an ingredient chip — no source-tag chip (that's cmm-4).
6. Tap manual-timer icon → enter "5 minutes", label "Test" → start.
   Active timer chip appears in the row above the strip.
7. Tap the chip → detail sheet shows label, countdown, Cancel,
   Restart. Tap Cancel → chip disappears.
8. Open overflow → Reset cook → confirm. State resets to step 0.

## Smoke 3 — Partial-load degrade (~3 min)
**Hard to reproduce naturally.** If you have a way to delete one
recipe between meal-load and cook-mount (or modify a fixture), use
that. Otherwise, the automated test
`partial failure: banner + cook UI mounts + placeholder` covers this
fully.

Manual test if possible:
1. Open a meal with one component whose recipe has been archived /
   deleted.
2. Cook UI mounts. Top of screen: amber banner reading
   "<ComponentName> couldn't load — some steps may be unavailable" +
   Retry button.
3. Step card initially shows the working component's first step.
4. Tap Next until you reach the failed component's range → step card
   swaps to a placeholder card "<ComponentName> couldn't load — Some
   steps may be unavailable for this component" + Retry button.
5. Tap Retry → spinner spins, then either error stays (still failing)
   or the placeholder is replaced by the now-loaded component's first
   step. Verify no other component's state was reset (try this AFTER
   advancing other components' steps).

## Smoke 4 — Offline cook (~2 min)
1. Cook a meal once online so the recipes get cached locally.
2. Force-quit. Switch device to airplane mode.
3. Re-open the app → tap the meal → tap Start Cooking → cook UI
   mounts with "Offline" badge in the header.
4. Step card shows the cached first step.

## Negative
- No section header above step card (cmm-3 territory).
- No "from <component>" tag chips on ingredients (cmm-4).
- No "Finish cooking now" overflow item (cmm-6).
- No Resume gate sheet on entry (cmm-7).

## Automated coverage
- `flutter test test/meal_cook_mode_test.dart` — 5 tests pass (mount,
  all-failure, partial-failure + placeholder, retry-remap, offline,
  banner-retry).
- `flutter test test/cook_plan_test.dart` — placeholder-slot contract
  covered.
- `flutter test test/features/meals/meal_detail_screen_test.dart` — 4
  FAB visibility tests pass.

## Sign-off
Story is shippable when smokes 1, 2 pass and the automated suite is
green. Smokes 3 and 4 are nice-to-have manual confirmations of
behaviour the automated suite already verifies.
