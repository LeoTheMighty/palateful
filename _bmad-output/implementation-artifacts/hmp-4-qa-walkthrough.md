# Story hmp-4 — QA Walkthrough

**Status:** ready for QA
**Commit:** (filled in at commit time)

## Pre-check

- Home has mixed tiles: at least 3 recipes + 1 Meal whose components
  reference 2 of those recipes; leaves at least 1 uncombined recipe.

## Walkthrough

### Show type chip wrap

1. Tap the filter pill (top-right, Icons.tune). Sheet opens.
2. Find the new **Show** section between Sort by and Meals. Verify
   three chips: `All`, `Recipes only`, `Meals only`. Only one chip is
   highlighted at a time.
3. Tap `Meals only` → Apply. Grid shows only Meal tiles. Filter pill
   shows the active dot.
4. Reopen sheet → tap `All` → Apply. Grid restores.
5. Tap `Recipes only` → Apply. Grid shows only RecipeCard tiles;
   MealTiles disappear. Pill active.
6. Reopen → tap `All` → Apply. Grid restores.

### Hide components of Meals toggle

7. Open sheet; find **Hide components of Meals** toggle right below
   the Show chips. Subtitle reads "Hide recipes that are part of any
   Meal." Toggle OFF by default.
8. Flip toggle ON → Apply. Component recipes disappear from the grid
   (those referenced by at least one Meal). Meal tile stays;
   uncombined recipe stays. Active dot present.
9. Reopen → flip toggle OFF → Apply. Recipes come back; dot clears
   (assuming other filters are also default).

### Clear all + Undo

10. Set some non-default state (e.g., Meals only + hide components).
11. Tap Clear all → Apply. Snackbar "Sort & filters cleared" with an
    Undo action.
12. While snackbar is visible, tap Undo. Home state rolls back — both
    new filters reapplied. Pill active dot present again.

### Zero-Meal fixture

13. Clear all Meals (or use a fresh account with no Meals). Home grid
    shows only RecipeCards.
14. Open sheet → flip Hide Components ON → Apply. Grid unchanged
    (there's nothing to filter against).
15. Open sheet → tap Meals only → Apply. Grid renders empty-state
    (no MealTile + no RecipeCard). Returning to `All` restores the
    recipe grid.

### A11y sanity

16. VoiceOver / TalkBack the Show chips — each reads its label.
17. Read the SwitchListTile: "Hide components of Meals, Hide recipes
    that are part of any Meal, switch, off/on."

## Pass criteria

- ✅ Steps 1–17 all behave as described.
- ✅ No unexpected network calls while toggling filters (filtering is
  purely client-side).
- ✅ FilterPill dot reflects current non-default state.
- ✅ Clear all + Undo both route through both new fields.
