# Story hmp-3 — QA Walkthrough

**Status:** ready for QA
**Commit:** (filled in at commit time)

## Pre-check

- Home renders recipes + at least one Meal (Kale Salad Meal with Kale
  Salad + Lemon Dressing components).
- At least one recipe (Miso Broccoli) exists outside the Meal so the
  add-to-meal flow has something to add.

## Walkthrough

### Create Meal

1. Long-press Kale Salad → bulk bar docks; bar primary reads "Bulk
   action unavailable" (1 recipe only).
2. Tap Lemon Dressing → primary reads **Create Meal**.
3. Tap Create Meal → `CreateMealSheet` modal opens pre-filled with
   Kale Salad + Lemon Dressing as components. Name field reads
   "Kale Salad + Lemon Dressing" and is autofocused.
4. Type "Kale Salad Meal" → tap Create. Sheet dismisses. Selection
   clears automatically. Grid reloads with the new Meal tile at the top.

### Add to Meal — happy path

5. Long-press Kale Salad Meal → bar primary reads "Select recipes to
   add to this Meal" (disabled).
6. Tap Miso Broccoli → bar primary reads **Add to "Kale Salad Meal"**.
7. Tap Add to Meal → snackbar "Added 1 recipe to Kale Salad Meal."
   Selection clears. The Meal tile's chip row updates to include
   Miso Broccoli (grid reload is automatic).

### Add to Meal — dedup short-circuit

8. Long-press Kale Salad Meal, then tap Kale Salad (already a
   component). Tap Add to Meal.
9. Snackbar reads "All selected recipes are already in this Meal." No
   API call fires (confirm via network tab or logs). Selection clears.

### Add to Meal — partial failure (manual — requires forced API error)

10. Stub the backend to return 403 on `POST /v1/meals/{id}/recipes`
    for the second of two selected recipes.
11. Long-press Kale Salad Meal, tap two recipes neither already in the
    Meal, tap Add to Meal.
12. Snackbar: "Added 1 of 2 — see details" with a View action.
13. Tap View → dialog "Some recipes could not be added" lists the
    failed recipe with reason "You can't edit this recipe."
14. Tap Dismiss → dialog closes; selection has already cleared; grid
    reload reflects the successful add.

### Archive — happy path

15. Long-press a recipe, tap 4 more recipes and 1 Meal.
16. Tap Archive → confirm dialog "Archive 5 recipes and 1 Meal? You
    can restore them later from Archive."
17. Tap Cancel → dialog closes, selection intact, nothing archived.
18. Tap Archive again, then Archive (accept) → snackbar "Archived 6
    items." Selection clears; all 6 items vanish from the grid; they
    appear in the Archive tab.

### Archive — partial failure (manual — requires forced error)

19. Stub backend to 409 on `POST /v1/meals/{id}/archive`.
20. Select 1 recipe + 1 Meal → Archive → confirm.
21. Snackbar: "Archived 1 of 2 — see details" with View.
22. Dialog "Some items could not be archived" lists the Meal with
    reason "Conflict — try again."
23. Grid reload reflects recipe archived, Meal still present.

### Linear progress while working

24. With the network throttled, tap Add to Meal on 3 recipes. During
    the in-flight phase:
    - Bulk bar primary + Archive buttons are disabled (grey).
    - A thin `LinearProgressIndicator` renders at the top of the bar.
    - Tapping a RecipeCard in the grid still toggles selection.

### A11y sanity

25. VoiceOver / TalkBack → long-press enters selection mode, announces
    "Exit selection" on the X button, "Create Meal" / "Add to …" /
    "Archive selected" on bulk-bar buttons.

## Pass criteria

- ✅ All 25 steps behave as described.
- ✅ No unexpected network calls (network tab shows one
  add-recipe-to-meal POST per non-dedup'd recipe, one bulk/archive
  POST for the recipes collection, one archive POST per Meal).
- ✅ Selection always clears on success; persists on Cancel.
- ✅ No crashes if the user closes the confirm dialog with system back.
