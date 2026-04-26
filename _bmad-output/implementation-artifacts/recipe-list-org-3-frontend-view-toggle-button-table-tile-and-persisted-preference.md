# recipe-list-org-3 — Frontend: view toggle button + table tile + persisted preference

**Epic:** `epic-recipe-list-organization`
**Status:** done
**Order in epic:** 3 of 6

## Goal

Introduce the dual-density browse experience: users pick **grid** (the
existing visual layout) or **table** (denser one-row-per-recipe layout).
The choice is persisted globally per user and respected on cold-start.
This story ships the foundation — enum + persisted notifier + toggle
button + table-tile widget. Story 4 fills in the dynamic-column slot;
Story 5 layers the hide-in-meals chip; Story 6 sweeps for regressions.

## Scope — files this story touches

**NEW**
- `app/lib/features/home/recipe_list_view.dart` — `RecipeListView`
  enum, `loadSavedRecipeListView()` boot helper, and the
  `recipeListViewProvider` (Riverpod NotifierProvider).
- `app/lib/features/home/widgets/recipe_list_view_toggle_button.dart`
  — single-icon button (▦ ↔ ≡) with tooltip describing the next state.
- `app/lib/features/home/widgets/recipe_table_tile.dart` — compact row
  rendering thumbnail (40×40), title, books pill, and a `trailing`
  slot for Story 4's dynamic column.
- `app/test/features/home/recipe_list_view_test.dart`,
  `recipe_list_view_toggle_button_test.dart`,
  `recipe_table_tile_test.dart` — unit + widget coverage.

**MODIFY**
- `app/lib/main.dart` — load saved view at boot and pass it as an
  override on `recipeListViewProvider` (mirrors the
  `themeModeProvider` boot pattern so the first frame respects the
  user's last choice without flashing the default).
- `app/lib/features/home/home_screen.dart` — mount the toggle button
  next to the existing FilterPill in the search header; branch
  `_buildRecipeGrid()` on the watched view to render either the
  existing GridView or the new `_buildRecipeTable()` ListView.
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` —
  convert to `ConsumerStatefulWidget` to access `ref`; mount the
  toggle button in the AppBar actions; branch the body's mixed grid
  into `_buildMixedTable()` when the table view is active.

## Acceptance criteria

1. **Enum + provider.** `RecipeListView { grid, table }` defined; a
   `Notifier<RecipeListView>` exposes `toggle()` and `set(view)`.
   Default-constructed notifier defaults to grid; `main.dart` overrides
   it with the SharedPreferences-loaded value at boot.
2. **Toggle button placement.** `RecipeListViewToggleButton` mounted
   in both home (next to FilterPill) and recipe-book-detail (in the
   AppBar actions). Tapping flips the icon (▦ ↔ ≡), updates the
   tooltip ("Switch to table view" ↔ "Switch to grid view"), and
   persists the new value to SharedPreferences asynchronously.
3. **Table tile.** `RecipeTableTile` renders thumbnail (40×40), title
   truncated to one line, optional books pill (single book name from
   `recipe_book_name`; "+N" deferred — no cross-book payload exists
   today), and a `trailing` slot for Story 4. Falls back to a chevron
   when `trailing` is null. Selection state shows a primary-tinted
   background + a trailing check-circle.
4. **Cold-start persistence.** After toggling to table and restarting
   the app, the table view is the default on next boot. Implemented
   via `loadSavedRecipeListView()` called pre-`runApp` and used to
   override the provider's initial value.
5. **Both screens dual-render.** Home and recipe-book-detail each
   branch their existing recipe list rendering on the watched view.
   Grid path is unchanged behavior (zero-regression for existing
   tests). Table path uses `RecipeTableTile` rows separated by
   `Divider` lines.
6. **Coverage.** 19 new widget/unit tests cover enum default, override
   construction, `toggle()` persistence, no-op on same-state set,
   `loadSavedRecipeListView()` happy + bad-value paths, button icon
   swap, persisted-value respect, all four tile pieces, tap +
   long-press dispatch, and meal vs recipe placeholder icons.

## Implementation notes

- **Provider construction pattern.** Mirrors `themeModeProvider`: the
  Notifier accepts an optional `_initial` defaulting to `grid` so
  tests don't need to override anything. `main.dart` overrides at
  boot with the persisted value.
- **Persistence is best-effort.** A SharedPreferences write failure
  must NOT roll the in-memory state back — the user's tap should
  feel responsive even on a flaky plugin. Logged via swallow-and-
  continue (`try {} catch (_) {}`) inside `set()`.
- **Books pill data.** Today's payload only knows one book per recipe
  (home_content_provider sets `recipe_book_name` from the parent book
  fetch; book-detail injects the current book name). The "+N"
  multi-book affordance from the epic spec is deferred — it'd need a
  backend story to enrich each recipe row with its full
  recipe_book_ids list. Not blocking Story 3 acceptance.
- **Meals in table view.** The home recipe list mixes recipes + meals
  (post `_mergeRecipesAndMeals`). When toggled to table, meals render
  as `RecipeTableTile` rows with their first component image as the
  thumbnail and a `Icons.layers_outlined` placeholder when no
  components have an image. Same selection wiring as the grid path
  (long-press → `enterWith(kind:'meal', id:...)`).
- **No haptic doubling.** The grid path called both
  `HapticFeedback.selectionClick()` (in the wrapper) and
  `mediumImpact()` (inside RecipeCard's InkWell) on long-press. The
  table tile fires only the medium impact internally — single haptic
  feels better and matches the user's mental model that long-press
  is one gesture.
- **Recipe-book-detail conversion.** Only edit was changing `extends
  StatefulWidget` → `extends ConsumerStatefulWidget` (and the
  matching `State` → `ConsumerState`). Everything else compiles
  unchanged because `ref` is automatically available on
  `ConsumerState`.

## Tests added

`test/features/home/recipe_list_view_test.dart`:
- default-constructs to grid
- respects override at construction time
- `toggle()` flips state and persists
- `set()` is a no-op when already in target state
- `loadSavedRecipeListView()` returns grid when nothing persisted
- ...returns persisted table value
- ...falls back to grid on unrecognized value

`test/features/home/recipe_list_view_toggle_button_test.dart`:
- shows grid icon + correct tooltip by default
- tap flips icon, tooltip, and persisted value
- respects pre-set persisted value via override

`test/features/home/recipe_table_tile_test.dart`:
- renders title and books pill for a recipe with a book
- omits books pill when book name is missing
- renders chevron when no trailing widget supplied
- renders trailing widget in place of chevron
- shows check_circle when selected
- tap fires onTap
- long-press fires onLongPress
- renders meal placeholder icon when meal has no images
- renders recipe placeholder icon when no image_url

## Out of scope (handled in later stories)

- **Story 4** — `dynamicColumnFor(SortKey)` helper + filling the
  trailing slot + tapping the column header to flip sort direction.
- **Story 5** — `HideInMealsChip` + counter copy + empty-state.
- **Story 6** — regression sweep (long-press multi-select in table
  view; view-switch perf < 100ms).

## File list

- NEW `app/lib/features/home/recipe_list_view.dart`
- NEW `app/lib/features/home/widgets/recipe_list_view_toggle_button.dart`
- NEW `app/lib/features/home/widgets/recipe_table_tile.dart`
- MODIFY `app/lib/main.dart`
- MODIFY `app/lib/features/home/home_screen.dart`
- MODIFY `app/lib/features/recipe_books/recipe_book_detail_screen.dart`
- NEW `app/test/features/home/recipe_list_view_test.dart`
- NEW `app/test/features/home/recipe_list_view_toggle_button_test.dart`
- NEW `app/test/features/home/recipe_table_tile_test.dart`
- MODIFY `_bmad-output/implementation-artifacts/sprint-status.yaml`
