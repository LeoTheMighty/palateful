<!-- refined via party-mode 2026-04-25 (consolidated) -->
# Epic: Recipe List Organization — Hide-in-Meals + Grid/Table Toggle + Dynamic Sort Column

## Overview

Make the recipe list (home screen and inside-a-book) scale gracefully past ~30 recipes. Two complementary moves: (1) hide recipes that are already attached to a meal by default — meals are the curation cleanup verb, and a recipe inside a meal doesn't need to clutter the loose list; (2) introduce a Table view alongside the existing grid, with a single dynamic column whose label and values mirror the active sort, so the user's chosen lens always shows the relevant signal.

## Goal

Convert the recipe list from a discovery-grid-only surface into a dual-mode browse surface where the user picks density (grid for visual / table for at-a-glance) and the visible signal (the dynamic column = current sort). Crucially, no new column-picker UI, no new tag system — the sort *is* the lens.

## End-user flow

1. **User opens home or any recipe-book detail** → list defaults to grid view (current behavior preserved).
2. **In the header, next to the existing sort/filter funnel,** a new icon button shows `▦` (grid is active). Tapping it switches the icon to `≡` and the layout to a table view; tapping again toggles back. The choice is persisted per user.
3. **At the top of the list (any view),** a filter chip reads "*32 recipes · 8 hidden in meals*". Tapping the chip toggles whether meal-attached recipes are shown. Default: hidden.
4. **In table view,** each row shows a small thumbnail · recipe title (truncated to one line) · a compact "books" pill (e.g., "Trying Out" or "+2") · one **dynamic column** on the right.
5. **The dynamic column's header label and values follow the active sort:**
   - Sort by `Last cooked` → header reads "Last cooked", values show relative dates ("3 days ago", "—" if never cooked).
   - Sort by `Cook time` → header reads "Cook time", values show "30 min".
   - Sort by `Date added` → header reads "Added", values show relative dates.
   - Sort by `Title` (alpha) → header falls back to "Last cooked" since alpha is already obvious from the title column.
   - Sort by `Vibes` / `Best` (existing weighted-score sorts) → header reads the sort name, value is the score (or hidden if internal).
6. **Tapping the dynamic column header flips sort direction.** No separate sort/dir control — the table column and the sort menu are the same control surface.
7. **Long-press in either view** still enters the existing multi-select mode (covered in `epic-recipe-bulk-organize`); table rows become tappable selection targets, no other change.
8. **Recipes never cooked** sort to the bottom when "Last cooked" is the active sort and arrow is descending. (`NULLS LAST`.)

## Frontend changes

- New enum `RecipeListView { grid, table }` in a shared file under `app/lib/features/home/`.
- New persisted preference `recipe_list_view` (per user, via `SharedPreferences` or the existing user-prefs provider).
- New widget `RecipeListViewToggleButton` — single icon button, swaps `▦` ↔ `≡`, tooltip "Switch to table view" / "Switch to grid view"; placed in `home_screen.dart` and `recipe_book_detail_screen.dart` headers next to the existing filter funnel.
- New widget `RecipeTableTile` — compact row with thumbnail (40×40), title, books pill, dynamic-column trailing region.
- New helper `dynamicColumnFor(SortKey)` returning `(label, valueResolver)`.
- New filter chip `HideInMealsChip` rendered above the list in both views; reads the count of hidden recipes from the home content provider; on tap toggles the filter and updates the count copy.
- `home_screen.dart:1211-1235` — branch on `recipeListView` to render `GridView.builder` (existing) or `ListView.separated<RecipeTableTile>`; pull `last_cooked` from each recipe's payload (added in story `recipe-list-org-1`).
- `recipe_book_detail_screen.dart` — same dual-view branch.
- `home_content_provider.dart` — extend the recipe payload merge to include `last_cooked` from the new server-side join, plus an `is_in_meal` boolean for the hide-in-meals filter (sourced from the existing `meal_recipes` data already on the home payload).
- `filter_bottom_sheet.dart:9` — confirm the existing `SortKey` enum covers `lastCooked`; add it if missing.
- Empty-state: when "hide in meals" is on and the user has no loose recipes left ("everything is in a meal"), show a celebratory empty state with one tap to disable the filter.

## Backend changes

- **Recipe list endpoints** (`GET /v1/recipes`, `GET /v1/recipe-books/{id}/recipes`, plus the home-content composite endpoint): add `last_cooked: datetime | null` to each recipe row, computed via `LEFT JOIN LATERAL (SELECT MAX(cooked_at) FROM cooking_logs WHERE recipe_id = recipes.id AND archived_at IS NULL) cl ON TRUE`.
- **Sort by last_cooked**: extend the existing sort enum / order-by builder to support `last_cooked DESC NULLS LAST` (and ASC).
- **Hide-in-meals filter**: prefer client-side filtering using the existing `meal_recipes` join data already on the home payload (no API change). If that data isn't on every list endpoint, add an optional `?hide_in_meals=true` query param that excludes any recipe present in `meal_recipes`. Decide in story `recipe-list-org-2` after auditing what's already in the response.
- **Indexes** to verify exist (and add if missing):
  - `cooking_logs (recipe_id, cooked_at DESC) WHERE archived_at IS NULL` — supports the lateral join and sort.
  - `meal_recipes (recipe_id)` — confirmed exists per recon (`ix_meal_recipes_recipe_id`).
- **Performance gate**: list endpoint p95 must not regress > 50ms after the lateral join lands. Capture baseline before the change; verify post-change via `analyze_latency.py`.

## Infrastructure changes

None. No new env vars, no new AWS resources, no new pip deps. (Indexes ship via the existing migrator.)

## Initial design principles (from research + party-mode)

- **The sort is the lens.** No column-picker UI. Users already pick the lens via the existing sort menu; the table mirrors it.
- **Implicit `last_cooked` only.** Source from `cooking_logs` — every cook-mode session already writes one. No new "I cooked this without a meal" button in v1; if users miss it, follow up.
- **Hide-in-meals default-on.** Trust meals as the cleanup verb; show the counter chip so nothing feels lost.
- **Persisted preference per user, not per book.** A user is either a "table person" or a "grid person" globally.
- **Reuse, don't duplicate.** The filter pill bar, sort menu, multi-select, and home-content provider all stay; we extend.

## File structure

```
app/lib/features/home/
  recipe_list_view.dart                  # NEW — enum + persisted pref provider
  widgets/recipe_list_view_toggle_button.dart  # NEW
  widgets/recipe_table_tile.dart         # NEW
  widgets/hide_in_meals_chip.dart        # NEW
  home_screen.dart                       # MODIFY — branch on view enum, render chip
  home_content_provider.dart             # MODIFY — surface last_cooked + is_in_meal
  widgets/filter_bottom_sheet.dart       # MODIFY — ensure last_cooked sort key exists
app/lib/features/recipe_books/
  recipe_book_detail_screen.dart         # MODIFY — dual-view branch
services/api/src/api/v1/recipe/
  list_recipes.py                        # MODIFY — last_cooked join, sort, optional filter
services/api/src/api/v1/recipe_book/
  list_recipes_in_book.py                # MODIFY — same
services/api/src/api/v1/home/
  get_home_content.py                    # MODIFY — same
services/migrator/migrations/versions/
  XXXX_index_cooking_logs_for_last_cooked.py  # NEW (if index missing)
```

## Stories

### `recipe-list-org-1` — Backend: `last_cooked` on list responses + sort + index

**Acceptance:**
- All recipe-list endpoints return `last_cooked: datetime | null` per row, sourced from `MAX(cooking_logs.cooked_at)` per recipe.
- `?sort=last_cooked&dir=desc|asc` supported (NULLS LAST on desc, NULLS FIRST on asc — the natural ordering for "most recently cooked at top, never-cooked at bottom").
- Index on `cooking_logs(recipe_id, cooked_at DESC) WHERE archived_at IS NULL` exists (added if missing).
- p95 of `GET /v1/recipes` and `GET /v1/recipe-books/{id}/recipes` does not regress > 50ms vs. baseline (capture pre-change via `analyze_latency.py --section endpoints --window 24h --format csv`).
- 100% coverage on touched code.

### `recipe-list-org-2` — Backend: hide-in-meals filter (server or client decision)

**Acceptance:**
- Audit: confirm whether the home-content payload already includes per-recipe `meal_recipe` membership info. If yes, no API change — note in story body. If no, add `?hide_in_meals=true` query param to the list endpoints.
- If server-side: filter via `WHERE NOT EXISTS (SELECT 1 FROM meal_recipes WHERE recipe_id = recipes.id)`.
- The endpoint also returns a `total_in_meals` count so the client can render "32 recipes · 8 hidden in meals" without a second call.
- Test: recipe attached to one meal does not appear in the filtered response; total_in_meals counts correctly.

### `recipe-list-org-3` — Frontend: view toggle button + table tile + persisted preference

**Acceptance:**
- New `RecipeListView` enum + `recipeListViewProvider` persisted via `SharedPreferences`.
- `RecipeListViewToggleButton` placed in home + recipe-book-detail headers; tapping toggles the enum + persists.
- `RecipeTableTile` widget renders thumbnail + title + books pill + dynamic-column slot. Title truncates to one line; books pill shows "+N" when >1 book.
- Cold-start: app respects the persisted preference.
- Widget tests: toggle changes view; table tile renders with all four pieces; tapping a tile opens recipe detail same as grid.

### `recipe-list-org-4` — Frontend: dynamic column mirrors active sort

**Acceptance:**
- `dynamicColumnFor(SortKey)` returns `(label, valueResolver)` for each sort: `lastCooked`, `cookTime`, `dateAdded`, `title` (falls back to `lastCooked`), `vibes` / `best` (uses sort name + score).
- Table view renders the resolved column; tapping the column header flips sort direction (calls into the existing sort provider).
- Sort change re-renders the dynamic column header + values atomically.
- Recipes with `last_cooked = null` render "—" in the cell when sorted by last_cooked, and sort to the bottom on desc.

### `recipe-list-org-5` — Frontend: hide-in-meals filter chip + counter

**Acceptance:**
- `HideInMealsChip` renders above the list in both views; copy: "*N recipes · M hidden in meals*" when filter active, "*N recipes · M shown in meals*" when off.
- Default: filter is ON.
- Tapping the chip toggles state; counts update from provider data.
- When N=0 and filter is on (everything is in a meal), an empty-state appears with a tap target to turn off the filter.
- Widget tests cover all four states (filter on/off × meals present/absent).

### `recipe-list-org-6` — Regression sweep + table view smoke

**Acceptance:**
- Long-press multi-select works in table view exactly as in grid (verifies the bulk-action-bar surface stays intact).
- Existing search, filter, archive flows unchanged in either view.
- Performance: switching views on a 200-recipe book completes in < 100ms (no re-fetch, just layout swap).
- Smoke flow: fresh app → toggle to table → sort by last cooked → confirm dynamic column updates → toggle to grid → confirm preference persists across app restart.

## Dependencies

- **Soft:** `epic-recipe-default-books` should land first so the system books exist when the user toggles between them; not a hard dependency, but the table view shines once the user has Favorites + Trying Out + their own books.
- **Hard:** none.

## Open questions for the user

None — all locked in the 2026-04-25 PRD addendum.

## Lenses (party-mode coverage check)

- **PM (John):** confirmed grid-vs-table is a per-user choice, not per-book; confirmed dynamic column is the central UX bet.
- **UX (Sally):** confirmed icon-only toggle (no text label), tooltip for a11y; confirmed empty-state when filter hides everything.
- **Frontend (Amelia):** confirmed reuse of existing sort/filter provider; new tile widget is the only structural addition.
- **Backend (Winston):** locked the lateral-join-for-last-cooked pattern + the p95-no-regress gate.
- **QA (Quinn):** test plan covers view persistence, sort-flip-via-column-header, hide-in-meals chip states, last_cooked NULLS LAST.
- **Infra:** None.
