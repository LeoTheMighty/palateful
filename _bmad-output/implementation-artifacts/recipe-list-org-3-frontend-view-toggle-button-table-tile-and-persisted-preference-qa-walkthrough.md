# QA — recipe-list-org-3 (view toggle + table tile + persisted preference)

Time-boxed: ~10 minutes. The whole story ships *foundation* — the
trailing dynamic column (Story 4) and the hide-in-meals chip (Story
5) are not yet wired in, so don't grade those.

## Smoke (3 min)

1. **Cold-start defaults to grid.** Fresh install (or wipe app
   storage), open Palateful, land on Home. Grid view renders. The
   header has the recipe-books icon, search field, pantry icon, the
   sort-funnel pill, and *new* — a circular **▦ (Icons.view_module)**
   button to its right. Hover (or long-press for tooltip) reads
   "Switch to table view."
2. **Tap toggles to table.** Tap the ▦ button. The grid swaps to a
   single-column list of rows: small thumbnail · recipe title · books
   pill · trailing chevron. The header icon flips to **≡
   (Icons.view_list)**, tooltip reads "Switch to grid view." No
   network request fires (verify in Charles / network panel — only
   the in-memory state changes).
3. **Tap toggles back.** Tap ≡; the layout returns to grid.

## Persistence (1 min)

1. With table view active, fully kill the app (swipe out of recents
   on iOS, force-stop on Android).
2. Reopen the app. Home should land directly on **table** view — no
   single frame of grid flash. The toggle icon shows ≡.
3. Toggle back to grid; restart; should land on grid.

## Recipe-book detail surface (2 min)

1. Tap the recipe-books icon in the home header → tap any book →
   recipe-book detail screen opens.
2. The AppBar shows the existing icons plus the **toggle button**
   (▦ / ≡) inserted before the multi-select checklist icon. Same
   tooltip behavior.
3. Toggle the view here. Same dual-render — grid path is the existing
   `_RecipeCard` / `MealTile`; table path is one row per recipe / meal
   with the book name as the pill.
4. Toggle on the home screen too — both screens share the same
   preference (toggle on home, navigate to a book, the book is
   already in the matching view).

## Selection mode parity (2 min)

1. From the table view on home, **long-press** any recipe row. The
   row should highlight (primary-tinted background + check-circle on
   the right) and the bottom bar should show the bulk-action bar
   (Create Meal / Add to Meal / Archive / Add to / Move to). This is
   the same behavior as long-press in the grid.
2. Tap a few more rows; they get added to the selection.
3. Tap **X** in the AppBar (or the close affordance) to exit select
   mode. Selection is cleared.
4. Repeat the same flow in **grid view** to confirm parity.

## Meals in table view (1 min)

1. On home, if you have any Meals (`Add → New Meal`), they should
   render as table rows in table view too. Their thumbnail is the
   first component image (or a layered icon if no components have
   images). Tapping opens the meal detail.
2. Long-press a meal row in table view → bulk bar with Add to Meal /
   Archive enabled (matching grid behavior).

## Edge cases to spot-check (1 min)

- **No recipes.** A book with zero recipes + zero meals shows the
  same empty state in both views — the toggle button is still
  present in the AppBar but tapping it has no visible effect (the
  empty state spans full width regardless).
- **Single row.** A book with one recipe in table view renders one
  row + chevron, no Divider above or below.
- **Long titles.** A recipe with a 60+ character title truncates at
  one line with ellipsis (does not wrap, does not push the books
  pill off-screen).

## Pass criteria

- ✅ Toggle present + functional in both screens.
- ✅ Persistence survives a cold restart with no flash.
- ✅ Long-press multi-select works in table view (parity with grid).
- ✅ No layout overflow / wrap on long titles.
- ✅ No new analyzer warnings on the touched files.
- ✅ Dynamic-column slot empty in this story (chevron renders) —
  Story 4 will populate it.
