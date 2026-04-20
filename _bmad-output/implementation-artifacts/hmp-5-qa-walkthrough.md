# Story hmp-5 — QA Walkthrough

**Status:** ready for QA
**Commit:** (filled in at commit time)

## Pre-check

- Zero-Meal fixture (new account) is available.
- Mixed fixture (recipes + at least 1 Meal) is available.
- At least one device with VoiceOver / TalkBack for the a11y sweep.

## Walkthrough

### Zero-Meal regression

1. Sign in on a new / meal-less account. Home grid renders RecipeCards
   only. No MealTile anywhere in the grid.
2. Tap the filter pill. Confirm **Show** section + **Hide components
   of Meals** toggle render. Flip "Hide components" ON → Apply. Grid
   unchanged (no-op with zero Meals). Filter pill dot ON.
3. Reopen sheet → `Meals only` → Apply. Grid goes empty (no Meals
   exist). Dot stays ON.
4. Reopen sheet → `All` → toggle Hide components OFF → Apply. Grid
   restores. Dot clears.
5. Long-press a RecipeCard. Selection app bar swaps in: "1 selected"
   with X. Bulk bar primary reads "Bulk action unavailable" (tooltip
   teaches the rule). Archive enabled.
6. Tap X → exits. Home returns to unselected state.

### Selection + filter orthogonality

7. Apply `Meals only` filter (do this BEFORE entering selection). Grid
   shows Meals only.
8. Long-press a Meal → selection app bar + bulk bar appear.
9. Tap X to exit selection. Filter remains `Meals only`.
10. Tap the filter pill → `All` → Apply. Grid restores.

### A11y sweep (iOS VoiceOver / Android TalkBack)

11. Long-press a recipe to enter selection mode.
12. Swipe to the X button in the app bar → reads "Exit selection,
    button." Double-tap → exits selection.
13. Re-enter selection. Swipe to the Archive button in the bulk bar →
    reads "Archive selected, button."
14. Swipe to a MealTile that renders in your grid. The "Meal" pill
    (top-left) reads "Meal." The favorite star reads "Favorite" or
    "Unfavorite" depending on state; toggling fires an optimistic
    update.
15. Swipe to the bulk bar's primary slot. When disabled, it reads the
    teaching tooltip verbatim ("Select 1 more recipe to create a
    Meal, or select a Meal to add to").

### Epic-wide happy-path

16. On the mixed fixture, long-press two recipes. Tap Create Meal.
17. `CreateMealSheet` opens pre-filled. Name field reads the joined
    "A + B." Type a unique name + Create. Sheet dismisses. Grid
    reloads with the new Meal tile.
18. Long-press the new Meal, tap a recipe not already in it. Tap Add
    to Meal. Snackbar "Added 1 recipe to <name>." Meal chip row
    updates on next load.
19. Long-press a recipe + the Meal. Tap Archive. Confirm. Snackbar
    "Archived 2 items." Both vanish from home; both appear in Archive.

### Integration test

20. With a real backend running + fixture data loaded (≥2 recipes),
    `flutter test integration_test/meals_home_promotion_flow_test.dart`
    walks steps 16–17 automatically and asserts the new Meal appears
    in the grid after creation.

## Pass criteria

- ✅ Steps 1–20 all behave as described.
- ✅ No unexpected network calls during filter toggling.
- ✅ Selection persists across entering/exiting selection; no lingering
  state when selection ends.
- ✅ VoiceOver / TalkBack announces every enumerated semantic label.
- ✅ Integration test either passes (backend present) or self-skips
  cleanly (backend empty).
