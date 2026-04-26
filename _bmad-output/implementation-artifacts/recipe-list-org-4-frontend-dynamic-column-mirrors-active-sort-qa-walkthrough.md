# QA — recipe-list-org-4 (dynamic column mirrors active sort)

Time-boxed: ~8 minutes. Story 3 must be visible (toggle to table)
before any of this is testable.

## Setup

- A book with at least 6 recipes — some you've cooked recently (within
  the past week), some you've cooked once, and at least one you've
  *never* cooked (no cooking-log entries). If you don't have one, log
  a few cooks via Cook Mode / `cooked_at` updates first.
- Toggle Home into table view (Story 3's ▦/≡ button).

## Header rendering (2 min)

1. With the default sort (**Best**), the table header on the right
   reads **"COOKED ↓"** (or "Cooked" — case may differ; the arrow is
   what matters).
2. Open the sort/filter funnel. Pick **Last cooked**. Apply.
3. Header should snap to **"LAST COOKED ↓"** in the same frame the
   row order changes. Recipes you cooked yesterday should be at the
   top; "never cooked" recipes should be at the bottom and show
   "—" in the right column.
4. Pick **Quickest** in the funnel → header reads "COOK TIME ↓",
   per-row values show "30 min" / "—".
5. Pick **Newest** → header "ADDED ↓", per-row values relative
   dates from creation.
6. Pick **Popular** → header "POPULAR ↓", values like "4.7".
7. Pick **Random** → rows shuffle, header falls back to "LAST
   COOKED ↓" (random has no meaningful per-row value).

## Header tap → flip direction (2 min)

1. With sort = **Last cooked**, tap the header. Arrow flips to ↑;
   row order reverses (oldest cooked at top), null-cooked rows now
   appear at the **top** with "—" (NULLS FIRST per epic).
2. Tap again. Arrow flips back to ↓, NULL rows back to bottom.
3. Switch to **Quickest** via the funnel. Direction resets to ↓
   (natural; shortest time first). Tap header → arrow ↑, longest
   first.
4. Switch to **Random**. Direction reset; tap is a no-op visually
   for random — order is shuffled, arrow is informational only.
5. Toggle to grid view, sort = Best. Toggle back to table — direction
   should still be ↓. (`_sortReversed` is reset on sort *change*,
   not on view toggle.)

## Meals + nulls + edge cases (2 min)

1. With sort = **Last cooked**, scroll to find any **Meal** rows.
   Their trailing slot should show the **chevron** (>) — meals
   don't carry `last_cooked` / `cook_time`. The chevron means
   "drill in" not "no value."
2. Find a recipe you've never cooked. With sort = Last cooked ↓ it
   should be at the bottom; cell shows "—". Flip to ↑; it should
   move to the top.
3. With sort = **Cook time** (Quickest), find a recipe with
   `prep_time = null` or `cook_time = null`. Cell should still show
   the non-null half (or "—" if both missing).

## Book-detail surface (1 min)

1. Open any recipe book → toggle to table view.
2. Header reads **"UPDATED ↓"** — non-tappable (book detail has no
   sort menu). The arrow is informational.
3. Each row's trailing shows the relative date of `updated_at`
   ("3d ago", "Yesterday", etc.). Same vocabulary as the home
   table column.
4. Edit a recipe → return to the book. The edited row jumps to the
   top with "Just now" (or matches when refresh fires).

## Pass criteria

- ✅ Header label + every row value updates **atomically** when sort
  changes (no flash of stale data).
- ✅ Header tap flips arrow + reorders rows in the same frame.
- ✅ NULLs anchor to the **right end** of the sort regardless of
  direction (last on desc, first on asc).
- ✅ Meals show the chevron, not "—", in the trailing slot.
- ✅ Book detail mirrors the home column vocabulary.
- ✅ Direction resets when sort changes via the bottom sheet, but
  preserves across grid↔table toggles.
- ✅ No new analyzer warnings on the touched files.
