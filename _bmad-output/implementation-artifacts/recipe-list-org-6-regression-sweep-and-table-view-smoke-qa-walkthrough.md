# QA — recipe-list-org-6 (regression sweep + smoke)

Time-boxed: ~10 minutes. This is the closing pass for the entire
epic — Stories 3, 4, 5 must already be visible in the build.

## Pre-flight

- Make sure `flutter test test/features/home/
  test/features/recipe_books/` is green (183 tests).
- A book with 30+ recipes makes the perf observation meaningful.
- A few recipes that are attached to meals (any recipe in any meal
  exercises the chip).

## Selection in table view (3 min)

1. Toggle Home to table view.
2. **Long-press** any recipe row. Expect:
   - Row highlights (primary-tinted background + check-circle).
   - Bottom bar shows the bulk-action bar (Create Meal / Add to /
     Move to / Archive).
   - Top app bar swaps to the selection app bar with "1 selected".
3. Tap a few more rows; counts climb.
4. Toggle to grid view (▦ / ≡ button). The same selection should be
   visible in grid form (same recipes highlighted).
5. Toggle back to table. Selection persists.
6. Tap **X** in the selection app bar → exit selection mode → grid
   density returns.
7. Repeat the same test starting from the grid view. Both directions
   should preserve selection across the toggle.

## Search + filter parity (2 min)

1. Toggle to table view. Open the sort/filter funnel (the sliders
   icon). Pick **Meals only**. Apply.
2. Table now shows only meal rows. Toggle to grid → still only meals.
3. Open funnel → switch back to **All**. Apply. All recipes return.
4. Toggle the **HideInMealsChip** off → meals' component recipes
   reappear. Toggle on → vanish again. (Story 5 surface, but verify
   it cooperates with the table layout.)
5. Open funnel → pick a vibe. Confirm the table reflows to that
   vibe only.

## Archive flow (1 min)

1. With table view, long-press a recipe → tap **Archive** → confirm.
2. Recipe disappears from the list (in both views — toggle to
   verify).
3. Open Archived Recipes (via menu) → the recipe is there.
4. Restore it → returns to the table view.

## Perf observation (2 min)

1. Open a book with 100+ recipes (or scroll the home grid in a
   real account). Toggle table → grid → table → grid 5 times.
2. Each toggle should feel instant — no spinner, no re-fetch
   indicator (no `RefreshIndicator` flash, no skeleton).
3. If you can stream Flutter DevTools' performance overlay, no
   frame should drop more than 16ms during the toggle (the perf
   test gate is < 100ms for the layout swap on 200 recipes).

## Cold-start persistence (1 min)

1. Toggle to **table** view on Home.
2. Force-quit the app.
3. Relaunch. Should land directly on table view, no flash of grid.
4. Toggle to grid; force-quit; relaunch. Should land on grid.

## Smoke flow — the epic's "happy path" (1 min)

1. Fresh app → toggle to table.
2. Open the sort funnel → pick **Last cooked** → Apply. The dynamic
   column header reads "LAST COOKED ↓". Recipes sort with most-
   recently-cooked at top, never-cooked at bottom (showing "—").
3. Tap the column header. Arrow flips to ↑; never-cooked recipes
   move to the top.
4. Tap again → ↓ → never-cooked back to bottom.
5. Toggle to grid view — the same sort is preserved (rows in the
   same order, just at grid density).
6. Cold-restart the app. Land on grid (since you toggled there
   last). Sort is back to **Best** (sort isn't persisted globally,
   only the view enum is — which matches the epic spec).

## Pass criteria

- ✅ Long-press selection works in both views and across toggles.
- ✅ Search / filter / archive flows are unchanged.
- ✅ View toggle is visually instant; no re-fetch.
- ✅ Persistence survives a cold restart.
- ✅ Dynamic column header + values update atomically when sort
  changes.
- ✅ Hide-in-meals chip cooperates with table layout.
- ✅ All 183 home + book tests pass on `flutter test`.
- ✅ No new analyzer warnings on the touched files.
