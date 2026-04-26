# QA — recipe-list-org-5 (hide-in-meals chip + counter + empty state)

Time-boxed: ~7 minutes. Stories 3 + 4 should already be visible.

## Setup

- A recipe book with 5+ recipes; create at least one Meal that
  references 2-3 of those recipes (long-press → Create Meal works).
- A second recipe book with 0 meals.

## Default-on chip (2 min)

1. **Cold start home.** Above the recipe grid you should see a chip:
   - Eye-off icon (Icons.visibility_off_outlined).
   - Copy: "*N recipes · M hidden in meals*" — N = recipes you can
     see, M = recipes attached to meals.
2. **Recipes in meals are hidden.** The recipes that are components
   of the meal you created should NOT appear in the grid. The Meal
   tile itself still appears.
3. **Tap the chip.** Icon flips to eye-on (Icons.visibility_outlined),
   copy flips to "*N recipes · M shown in meals*", and the previously
   hidden component-recipes reappear in the grid. N grows by M.
4. **Tap again.** Back to hide-on; component recipes vanish.
5. **Open the sort/filter funnel.** Confirm the "Hide components of
   Meals" switch row is **gone** from the bottom sheet (the chip is
   the single surface now).
6. **Clear all** in the bottom sheet — the chip should still show
   hide-ON afterward (the new default).

## Counter math (1 min)

1. Hide chip ON: copy = "(visible) recipes · (hidden) hidden in meals".
2. Add a recipe to the Meal (via the meal detail "Add recipe to meal"
   path). Return to home — the chip's M count should incrementally
   grow by 1 and N should drop by 1, all without a manual refresh.
3. Remove a recipe from a meal — counts move the other direction.

## Empty state (2 min)

1. Pick a small book where you can attach **every** recipe to at
   least one meal. (Easiest: a 2-recipe book + 1 meal that contains
   both recipes.)
2. Open the book in detail view. With hide ON by default, the grid
   should be empty and the **HideInMealsEmptyState** should appear:
   - Celebration icon.
   - Headline "Everything is in a Meal".
   - Subhead "Loose recipes are tidied up. Tap to show them anyway."
   - Filled button "Show all recipes".
3. Tap the button. Grid reflows with all recipes visible; chip flips
   to OFF.
4. Tap the chip back to ON — empty state returns.

## Book-detail surface (1 min)

1. Open any book → confirm the chip renders above the grid (and
   above the table when toggled to table view).
2. Counter mirrors home — N is the visible-recipes count for *this
   book only*; M is the in-meal count from this book.
3. Toggle the chip — same behavior as home.

## Edge cases (1 min)

- **Empty book** (zero recipes, zero meals): the existing
  "no recipes yet" empty state still renders; the chip is shown
  with "0 recipes" copy.
- **Selection mode.** Long-press a recipe to enter selection. The
  chip should disappear (so the bulk bar surface is unobstructed).
  Exit selection — chip returns.
- **Pull to refresh.** Refresh the home; chip state survives (it's
  client-side only).

## Pass criteria

- ✅ Default ON on cold start.
- ✅ Tap toggles + counts update atomically.
- ✅ Copy correctly switches active vs inactive vocabulary, and
  drops the trailing clause when M = 0.
- ✅ Empty state appears only when the filter is the cause; "no
  recipes yet" otherwise.
- ✅ Bottom sheet no longer carries the hide toggle.
- ✅ Selection mode hides the chip; restores after exit.
- ✅ Book detail mirrors home behavior with counts scoped to the
  book.
- ✅ No new analyzer warnings on the touched files.
