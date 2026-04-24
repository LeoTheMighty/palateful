<!-- refined via party-mode 2026-04-20 -->
# Epic: Meals — Home Promotion (create, combine, and visually distinguish Meals on the home grid)

## Overview

Today Meals show up on the home grid as a `MealTile` with a 4-up collage hero and an "N recipes" badge — but home is read-only for Meals. To **create** a Meal the user has to navigate into a recipe book and long-press from the book's grid. To **add a recipe to an existing Meal** they have to open the Meal detail and hit "Edit → Add Recipe." Home is Leo's main entry point — it's where recipes from every book already live — and today it is not pulling its weight for the Meals feature.

This epic makes home the primary creation surface for Meals. It wires long-press multi-select on the home grid, a context-sensitive bulk action bar that computes its primary action from the selection contents (Create Meal vs. Add to Meal vs. Archive), two new client-side filters ("Show" type + "Hide components of Meals"), and a MealTile v2 refresh that leaks the component recipe names right on the card plus closes the favorite-overlay parity gap with RecipeCard.

**Goal (Day-1 user value).** When this epic ships, Leo can:

1. Long-press Kale Salad on home, tap Lemon Dressing, tap **Create Meal** in the bulk bar, name it, save — same flow he already knows from book detail.
2. Long-press an existing "Kale Salad Meal" tile on home, tap a new recipe ("Miso Broccoli"), tap **Add to "Kale Salad Meal"** — now it's a 3-component Meal.
3. Open the filter sheet and pick **Meals only** to see just his Meals, or flip on **Hide components of Meals** to declutter his grid (Kale Salad and Lemon Dressing disappear because they're already in the Meal; the Meal stays).
4. See at a glance which tiles are Meals — subtle accent border + a "Meal" pill in the top-left + component names as a muted subtitle ("Kale Salad · Lemon Dressing").
5. Favorite a Meal directly from the home grid, same star-tap pattern he uses for recipes.

**Scope boundary — critical.** This is a **Flutter-only** epic. Zero backend changes. Every backend capability it relies on already ships: `POST /v1/meals/{id}/recipes` (foundation mcv-3), `POST /v1/recipes/bulk/archive` (pre-existing), `POST /v1/meals/{id}/archive` (foundation mcv-2), `GET /v1/meals?scope=home` (md-3), `POST/DELETE /v1/meals/{id}/favorite` (foundation). If party-mode surfaces a need for a backend change, that is a question back to the user, not a scope expansion.

This epic does NOT touch recipe detail (Start Cooking + Archive actions already live there — confirmed in research), does NOT touch book detail's multi-select (untouched; still the book-scoped fast path), does NOT add a bulk-archive endpoint for Meals (client-iterates instead), does NOT add AI pairings (sharing-and-ai epic), and does NOT add a "Meals" tab (rejected — Meals live where recipes live).

## End-User Flow

### Primary path — combine two recipes you're already looking at

1. Leo opens the app. Home renders the same unified grid he sees today: recipes from all his books + Meals, sorted by `updated_at DESC`. No visible change yet.
2. Leo long-presses "Kale Salad." The home AppBar swaps from the normal header to a **selection AppBar**: leading X button, title "1 selected," no trailing icons. The Kale Salad tile gains a checkmark overlay. Haptic tick fires.
3. Leo taps "Lemon Dressing." The AppBar reads "2 selected." A bottom **bulk action bar** docks over the grid with three slots: **Create Meal** (primary, enabled), **Archive** (secondary, enabled), and a trailing overflow "…" (unused in v1 — reserved).
4. Leo taps **Create Meal**. The existing `CreateMealSheet` (foundation's widget) opens as a modal bottom sheet with Kale Salad + Lemon Dressing pre-filled as `initialComponents`. Target book is Kale Salad's book (the first-selected recipe's book); a small editable chip "Book: Dinners" lets Leo retarget if he wants. Name field is pre-populated with "Kale Salad + Lemon Dressing" (truncated 60 chars) and autofocused.
5. Leo types "Kale Salad Meal" and taps **Create**. The sheet dismisses; the grid reloads; selection mode exits automatically. A `MealTile` for "Kale Salad Meal" appears in the grid where the two recipes used to sit (both recipes are still there too — Meal creation does not archive components).

### Secondary path — grow an existing Meal

6. A week later Leo wants to add "Miso Broccoli" to his Kale Salad Meal. He opens home, long-presses the "Kale Salad Meal" tile. AppBar: "1 selected." Bulk bar: **Create Meal** is disabled (tooltip "Select 2+ recipes to create a Meal"), **Archive** is enabled.
7. Leo taps "Miso Broccoli." AppBar: "2 selected." Bulk bar primary now reads **Add to "Kale Salad Meal"** (the Meal's name flows into the label). He taps it.
8. The client dispatches `POST /v1/meals/{kale-salad-meal-id}/recipes` with `{recipe_id: miso-broccoli-id}`. On success a snackbar reads "Added Miso Broccoli to Kale Salad Meal." Selection mode exits. The MealTile's component chips refresh to read "Kale Salad · Lemon Dressing · +1."
9. If Leo had selected 3 recipes (Kale Salad Meal + two new recipes), the client iterates — one `add_recipe_to_meal` call per new recipe_id. Client-side it pre-filters out any recipe_id already in the Meal's component list (409 avoidance). Any remaining failures — 409 for concurrent adds, 403 for permission shifts, 404 for archived-mid-flight — surface as a snackbar "Added 2 of 3 — see details" with a details dialog listing the failed recipe + reason.

### Filter path — scope the grid

10. Leo opens the existing filter pill (header icon with `Icons.tune`). The `FilterBottomSheet` renders with a new section **Show** positioned between Sort and Meal type: three single-select chips `[All | Recipes only | Meals only]`, default "All."
11. Below that, a toggle row reads **Hide components of Meals**, default OFF with a subtitle "Hide recipes that are part of any Meal."
12. Leo picks "Meals only" and taps Apply. The grid filters client-side: every RecipeCard disappears, only MealTiles remain.
13. Leo re-opens the sheet, flips back to "All," and flips **Hide components of Meals** ON. Grid refilters: Meals render normally; recipes whose `id` is in any Meal's component list disappear. His Kale Salad and Lemon Dressing and Miso Broccoli are gone; his Kale Salad Meal is still there alongside uncombined recipes.
14. The filter pill shows its existing "active" dot when either new filter is in a non-default state.

### Selection path — bulk archive across types

15. Leo long-presses a recipe he doesn't want anymore. Taps 4 more recipes and 1 Meal he's also done with. Bulk bar: **Create Meal** disabled (can't Create a Meal with a Meal in the selection), **Archive** enabled.
16. Leo taps **Archive**. Confirmation dialog: "Archive 5 recipes and 1 Meal? You can restore them later from Archive." He confirms.
17. Client dispatches in parallel: one `POST /v1/recipes/bulk/archive` with the 5 recipe_ids + one `POST /v1/meals/{meal-id}/archive` for the Meal. Same partial-failure snackbar pattern.

### MealTile v2 at rest

18. An unselected MealTile in the grid shows: the existing 1/2/3/4-up component collage hero, a **translucent white "Meal" pill** in the top-left corner with `Icons.layers_outlined`, a 2-px muted-primary accent border, the Meal name (existing), a **new component-chips row** below the name ("Kale Salad · Lemon Dressing · +1"), and a **tap-to-favorite star** overlay in the top-right matching RecipeCard's existing star position and behavior.
19. Tapping the tile body opens `/meals/:id` (unchanged). Tapping the favorite star toggles `meal_favorites` via the existing foundation endpoints; optimistic update, error-rollback.

### What does not change

The home grid layout (2-col responsive), the merge-by-`updated_at` logic, the search bar, the filter pill's position, the favorites carousel, the book grid's own multi-select flow, the recipe detail screen (Start Cooking + Archive stay there), the Meal detail action bar. If the user has zero Meals, the home grid is bit-identical to today — long-press still enters selection mode, but the "Add to Meal" primary action path is unreachable and no Meal-specific visuals ever render.

## Frontend Changes

All work under `app/lib/features/home/` and `app/lib/features/meals/widgets/`. One cross-reference into `app/lib/features/recipes/` (RecipeCard on home already exposes selection-state props — if not, add them there). Estimated LoC: ~600 lines new, ~150 modified.

### New files

- **`app/lib/features/home/widgets/home_selection_controller.dart`** — `ChangeNotifier` (or Riverpod `StateNotifier`) holding `_isSelectMode: bool`, `_selectedRecipeIds: Set<String>`, `_selectedMealIds: Set<String>`. Exposes `toggleRecipe`, `toggleMeal`, `enterWith(kind, id)`, `exit()`, and **computed getters**:
  - `selectionShape: SelectionShape` — enum `{ empty, singleRecipe, multipleRecipesOnly, singleMeal, singleMealWithRecipes, multipleMeals, mealsAndMeals }`
  - `primaryAction: BulkPrimaryAction` — enum `{ createMeal, addToMeal(Meal), disabled(String reason) }` — this is the contract the bulk bar reads.
- **`app/lib/features/home/widgets/home_bulk_action_bar.dart`** — bottom-docked `Material` card with two slots: primary (Create Meal | Add to "<name>" | disabled-with-reason) and secondary (Archive). Renders via `Positioned`+`SafeArea` at the bottom of the home `Stack`. Animates in/out on selection-mode toggle.
- **`app/lib/features/home/widgets/selection_app_bar.dart`** — the alternate AppBar rendered while `_isSelectMode` is true. Leading X, title "{N} selected," no trailing actions in v1.
- **`app/lib/features/home/widgets/bulk_partial_failure_dialog.dart`** — the "Added X of Y — see details" dialog body. Shared by Add-to-Meal and Archive flows. Accepts a `List<BulkOperationResult>` with `{targetName, success: bool, errorReason: String?}`.

### Modified files

- **`app/lib/features/home/home_screen.dart`** — wires the selection controller, swaps `AppBar` to `SelectionAppBar` when `_isSelectMode`, wires long-press on recipe and Meal cells to `controller.enterWith(...)`, passes selection state down to `RecipeCard` and `MealTile` so they render a checkmark overlay when selected, dispatches the bulk-bar primary action, applies the two new client-side filters (see filter section below), exits selection on successful bulk op. Retires `_showRecipeActions` (the old long-press sheet) — both its actions already exist on recipe detail per research.
- **`app/lib/features/home/widgets/filter_bottom_sheet.dart`** — extends `HomeFilterState` with `showType: ShowTypeFilter` (enum: all / recipesOnly / mealsOnly, default all) and `hideComponentsOfMeals: bool` (default false). Renders a new **Show** section between Sort and Meals (single-select chips) and a new toggle row right below it. Emits both on Apply.
- **`app/lib/features/home/home_screen.dart` (filter apply)** — `_applyFilters` gains two new filter steps:
  - If `showType == recipesOnly`: `items.where((i) => i.kind == 'recipe')`.
  - If `showType == mealsOnly`: `items.where((i) => i.kind == 'meal')`.
  - If `hideComponentsOfMeals == true`: compute `componentIds = _meals.expand((m) => m.components.map((c) => c.recipeId)).toSet()`; filter `items.where((i) => i.kind == 'meal' || !componentIds.contains(i.id))`.
- **`app/lib/features/meals/widgets/meal_tile.dart`** — adds:
  - A 2-px accent border (uses `colorScheme.primary.withOpacity(0.6)` or equivalent — confirm exact token with the existing theme file).
  - A "Meal" pill in the top-left: small `Container` with white backgroundColor at 0.88 opacity, 6-px rounded corners, `Icons.layers_outlined` at 14px + "Meal" text in `textTheme.labelSmall`.
  - A component-chips row below the name: single line, `textTheme.bodySmall` with `colorScheme.onSurfaceVariant`, joined by ` · `, truncated via ellipsis. If `components.length > 2`, render first 2 + `· +${components.length - 2}`.
  - A tap-to-favorite star overlay in the top-right matching RecipeCard's pattern verbatim. Constructor gains `isFavorited: bool` + `onFavoriteToggle: VoidCallback`.
  - A `selected: bool` prop — when true, render a checkmark overlay centered in the collage (same visual grammar as `_RecipeCard`'s selected state in book detail).
- **`app/lib/features/home/home_screen.dart` RecipeCard instantiation** — pass `selected: _selectionController.selectedRecipeIds.contains(r.id)` down; add `onLongPress` handler routing to `_selectionController.enterWith('recipe', r.id)` (if not already entered) or `toggleRecipe(r.id)` (if already in selection mode).
- **`app/lib/core/services/api_client.dart`** — no new methods (`addRecipeToMeal`, `bulkArchiveRecipes`, `archiveMeal`, `favoriteMeal`, `unfavoriteMeal` all exist). If any is missing per research it is an acceptance-criterion add-on for the corresponding story, not a new-file change.

### Selection state machine

```
empty
  ↓ long-press recipe →  { selectedRecipes: {r1}, mode: on }
  ↓ long-press meal   →  { selectedMeals: {m1},   mode: on }

any selection
  ↓ tap recipe (not selected) → add to selectedRecipes
  ↓ tap recipe (selected)     → remove from selectedRecipes
  ↓ tap meal   (not selected) → add to selectedMeals
  ↓ tap meal   (selected)     → remove from selectedMeals
  ↓ tap X in AppBar           → exit (empties sets)
  ↓ back gesture              → exit
  ↓ successful bulk op        → exit
```

### Primary-action resolution

```
recipes = selectedRecipes.length
meals   = selectedMeals.length

recipes >= 2 && meals == 0    → Create Meal (enabled)
recipes >= 1 && meals == 1    → Add to "<meal name>"
recipes == 0 && meals >= 1    → disabled, "Select 1+ recipes to add"
recipes == 1 && meals == 0    → disabled, "Select 1 more recipe to create a Meal"
meals >= 2                    → disabled, "Select only one Meal at a time"
empty                         → (bar hidden entirely — selection mode auto-exits on empty)
```

### Component-chips rendering spec

Given `MealSummary.components: List<MealComponentSummary>` with each carrying `name`:

```
0 components  → row hidden (impossible today; defensive)
1 component   → "Kale Salad"
2 components  → "Kale Salad · Lemon Dressing"
3 components  → "Kale Salad · Lemon Dressing · +1"
N > 3         → "Kale Salad · Lemon Dressing · +${N - 2}"
```

Ellipsis on overflow of a single `Text` row with `maxLines: 1, overflow: TextOverflow.ellipsis`. No word wrap.

### Empty / loading / error states

- **Long-press on loading tile**: if the tile is in a shimmer/placeholder state (e.g., image still loading), long-press is a no-op. Selection only activates on fully-loaded tiles.
- **Selection while a background refresh fires**: if `_meals` or `_recipes` reloads while selection is active, selected IDs that are still present stay selected; IDs that vanished (archived by another device, unshared book) are silently dropped from the selection sets. If the drop empties both sets, selection mode exits with a snackbar "Selection cleared — content changed."
- **Bulk bar during operation-in-flight**: all bulk-bar buttons disable; a thin linear progress indicator renders across the top of the bar. No double-submit possible.
- **Partial-failure dialog**: renders when `successes < total_attempts`. Lists each failed item by display name + a one-line reason ("Already in this Meal" / "You can't edit this recipe" / "Recipe was archived"). Dismiss returns to the grid with selection cleared.
- **Add-to-Meal with zero new recipes after client-side dedup**: if the user selected recipes that are ALL already in the target Meal, show a snackbar "All selected recipes are already in this Meal." No API call.
- **Filter with zero-Meal database**: "Show: Meals only" renders an empty grid with a muted empty state "No Meals yet. Create one by long-pressing two or more recipes." "Hide components of Meals" ON with zero Meals is a no-op (no IDs to filter against).
- **Filter active + bulk operation**: filters are purely presentational; they do not affect which IDs are selected. A recipe hidden by "Hide components of Meals" cannot be long-pressed (it's not rendered), but a recipe that was selected then filter turned on stays in the selection set. Selection persists across filter toggles.
- **Long-press on a MealTile while "Meals only" filter is active**: works the same — selection mode activates, selectedMeals gains the id. Since no recipes are visible, the bulk bar primary is always disabled until the user clears the filter.

### Widget tests (non-negotiable)

- `home_selection_controller_test.dart`: state transitions for every entry in the state machine; primary-action resolution for every row in the resolution table.
- `home_selection_mode_test.dart`: long-press a RecipeCard enters select mode, AppBar swaps, bulk bar appears. Tap adds/removes. Tap X exits. Back gesture exits. Successful bulk op exits.
- `home_bulk_action_bar_test.dart`: Create Meal enabled at 2R/0M; Add-to-Meal label shows Meal name at 1M/1R; disabled states render the correct tooltip for each selection shape; Archive always enabled when selection non-empty.
- `home_bulk_add_to_meal_test.dart`: client-side dedup removes already-in-Meal recipes; single add_recipe_to_meal call per remaining recipe; all-already-in-Meal triggers the "All selected recipes are already in this Meal" snackbar with no API calls; partial failure renders the dialog with exactly the failed rows.
- `home_bulk_create_meal_test.dart`: opens CreateMealSheet with correct initialComponents and target book; selected recipes persist in the sheet.
- `home_bulk_archive_test.dart`: confirmation dialog shows correct count; parallel dispatch to bulk-archive-recipes + individual archive-meal; partial failure dialog; selection clears on success.
- `filter_bottom_sheet_show_type_test.dart`: Show: All / Recipes only / Meals only toggles grid correctly; Hide components of Meals toggles; active-dot renders when either is non-default.
- `home_filter_hide_components_test.dart`: with zero Meals — toggle is a no-op; with 1 Meal (2 components) — 2 recipes disappear; Meals never disappear regardless of this filter.
- `meal_tile_v2_test.dart`: component chips render 0/1/2/3/4/5-component cases correctly; accent border present; Meal pill present with glyph + text; favorite star overlay renders + toggles + rolls back on error; selected-state checkmark overlay renders.
- `home_zero_meal_regression_test.dart`: zero-Meal fixture renders grid bit-identically to pre-epic baseline (no MealTile, no Meal filter has visible effect, long-press enters selection mode normally but bulk bar shows Create Meal disabled-with-reason for 1R or enabled for 2+R).

## Backend Changes

**None.**

Every endpoint this epic calls already exists:

- `GET /v1/meals?scope=home` — foundation (`list_meals.py` supports `scope=home`)
- `POST /v1/meals/{meal_id}/recipes` — foundation (`add_recipe_to_meal.py`, mcv-3)
- `POST /v1/recipes/bulk/archive` — pre-existing (`bulk_archive_recipes.py`)
- `POST /v1/meals/{meal_id}/archive` — foundation (`archive_meal.py`, mcv-2)
- `POST /v1/meals/{meal_id}/favorite`, `DELETE /v1/meals/{meal_id}/favorite` — foundation (mcv-3)

### Component-name resolution (party-mode decision: client-side join)

Research confirmed foundation's `MealSummaryResponse` includes `component_count` and up to four `component_image_urls`, but NOT component recipe names. The home grid needs component names for the new chip row (FR-HMP-5) without a backend schema extension. Party-mode resolved this with an **in-memory join against the home's already-loaded recipe list**:

- Home already fetches recipes from every readable book (via `_loadAllRecipesFromBooks(books)` → per-book `getRecipeBook(id).recipes`). This produces a flat `_recipes: List<Recipe>` state.
- For each Meal rendered on home, its `component_recipe_ids` (already on `MealSummary`) are looked up against a `Map<String, String>` of `recipeId → name` built once per grid-load from `_recipes`.
- **Fallback**: any component_recipe_id not in the map is an archived recipe (archived recipes are excluded from the home fetch) or a recipe from a book no longer shared. The chip row renders the available names in order, and for the first unknown component appends ` · (archived)` ONCE regardless of how many components are missing (avoids "archived · archived · archived" noise).
- The map rebuild on every grid-load is O(N) where N is total recipe count — cheap. The per-tile lookup is O(k) where k ≤ component count, typically 2–4. No measurable perf concern.

This approach **preserves the zero-backend claim** and has the side benefit of "component name updates propagate automatically" — if the user edits a component recipe's name, the MealTile's chips update on the next home grid reload without any Meal-side invalidation.

If this approach reveals a UX issue during implementation (e.g., the "(archived)" fallback is hit frequently enough to feel cluttered), the escape hatch is a strictly-additive backend story `hmp-0` to extend `MealSummaryResponse` with `component_preview_names: List[str]` — one response field, no migration, no new endpoint. Not in scope for v1; flagged as a known fallback.

## Infrastructure Changes

**None.**

No new tables, no migrations, no AWS resources, no env vars, no Docker changes, no CI changes. This epic adds a Flutter feature that uses existing endpoints. Ships via the standard Flutter build + release pipeline.

## Design Principles (refined via party-mode 2026-04-20)

1. **Home is where Meals get made.** Primary creation surface moves from book-detail-only to home + book-detail. Book detail's own multi-select remains; this is additive.
2. **Long-press is the only selection gesture.** No pencil toggle, no FAB. User's locked choice (2026-04-20).
3. **Old home long-press sheet is retired.** Start Cooking + Archive already live on recipe detail — confirmed in research at `recipe_detail_screen.dart:541-549` (FAB) and `:705-717` (overflow Archive). No action migration required; the home sheet was a duplicate.
4. **Bulk bar is context-sensitive, not option-heavy.** One primary action computed from selection; Archive is always-enabled secondary. Disabled-with-reason-tooltip is the primary teaching mechanism for the "Add to Meal" pattern.
5. **Add-to-Meal uses the selection as the anchor.** Selecting a Meal in the selection is how the user opts into the "grow this Meal" flow. No Meal-picker sheet from a pure-recipe selection (deferred Q1; recipe detail's overflow can gain "Add to Meal…" as a future follow-up, not in this epic).
6. **Filters are client-side.** Home already loads all Meals via `scope=home`; filtering is in-memory. The "Hide components of Meals" filter uses the same in-memory `meals` list to compute component IDs — no backend query needed.
7. **Component names resolve client-side too.** The MealTile's chip row builds names from home's loaded recipe map, not a new API field. Archived-component fallback is a single `· (archived)` suffix. Escape hatch `hmp-0` (additive backend field) is documented but not shipped.
8. **"N recipes" badge retires in favor of chips.** The chip row's `+N` suffix carries the count; retaining the badge alongside would be redundant. The "Meal" pill (top-left) is the primary "this is not a recipe" signal.
9. **Favorite parity is table stakes.** Close the MealTile favorite-overlay gap. RecipeCard already has the star; MealTile will match.
10. **Partial-failure surface is consistent.** One "Added/Archived X of Y — see details" snackbar + dialog pattern shared by Add-to-Meal and Archive. This pattern is worth locking here so future bulk actions across the app inherit it.
11. **Bulk bar in `Scaffold.bottomNavigationBar` slot, not Stack overlay.** The `CustomScrollView`-with-slivers architecture makes Positioned overlays fragile across gesture-nav configurations; the bottomNav slot is free today and is the clean home.
12. **Riverpod StateNotifier, not ChangeNotifier.** Matches the project convention — `HomeFilterState` and the recipe/meal providers are all Riverpod today.

## File Structure

```
app/lib/features/home/
  home_screen.dart                                 [MODIFY]  selection state wiring, filter apply,
                                                             retire _showRecipeActions, bulk dispatch
  widgets/
    home_selection_controller.dart                 [NEW]     state machine + primary-action resolver
    home_bulk_action_bar.dart                      [NEW]     bottom-docked bulk bar widget
    selection_app_bar.dart                         [NEW]     alternate AppBar for selection mode
    bulk_partial_failure_dialog.dart               [NEW]     shared dialog for Add-to-Meal + Archive
    filter_bottom_sheet.dart                       [MODIFY]  +Show section, +Hide components toggle

app/lib/features/meals/widgets/
  meal_tile.dart                                   [MODIFY]  v2: component chips, accent chrome, Meal pill,
                                                             favorite star overlay, selected-state checkmark

app/lib/features/recipes/widgets/
  recipe_card.dart (or home_screen.dart RecipeCard) [MODIFY] +selected:bool prop for checkmark overlay
                                                              (if the prop does not already exist)

app/test/features/home/
  home_selection_controller_test.dart              [NEW]
  home_selection_mode_test.dart                    [NEW]
  home_bulk_action_bar_test.dart                   [NEW]
  home_bulk_add_to_meal_test.dart                  [NEW]
  home_bulk_create_meal_test.dart                  [NEW]
  home_bulk_archive_test.dart                      [NEW]
  home_filter_hide_components_test.dart            [NEW]
  home_zero_meal_regression_test.dart              [NEW]
  filter_bottom_sheet_show_type_test.dart          [NEW]

app/test/features/meals/
  meal_tile_v2_test.dart                           [MODIFY]  extend existing meal_tile_test with v2 cases
```

## Stories

### Story hmp-1 — MealTile v2: component chips, accent chrome, favorite overlay, selected-state

**Goal**: A visible Day-1 polish win that does not depend on selection-mode wiring. Ships the new MealTile on its own so the visual refresh can hit user devices first.

**Acceptance criteria:**

- `MealTile` renders a 2-px accent border. **First**: read `app/lib/core/theme/theme.dart` to check whether a Meal-accent token already exists. If yes, reuse. If no, add a `MealAccent` token to theme.dart (light + dark) and reuse it here — this is a trivial theme addition, not a backend change.
- A "Meal" pill renders in the top-left corner: translucent white (0.88 opacity) backgroundColor, 6-px rounded corners, `Icons.layers_outlined` at 14-px + "Meal" text in `textTheme.labelSmall`. **Pill has a soft black drop shadow** (BoxShadow blurRadius 4, offset (0, 1), color black.withOpacity(0.25)) to guarantee contrast against both light and dark collage images. Widget test asserts pill renders with drop shadow.
- A component-chips row renders below the Meal name using the **client-side join from home's in-memory recipe map** (see Backend Changes § Component-name resolution). Single line of `Text`, `textTheme.bodySmall` with `colorScheme.onSurfaceVariant`. Format: up to 2 component names joined by ` · `; if >2 components, append ` · +${N-2}`. If one or more component_recipe_ids are not in the provided map, append ` · (archived)` once at the end regardless of how many. Ellipsis on overflow (`maxLines: 1, overflow: TextOverflow.ellipsis`).
- Constructor signature changes:
  - Gains `componentNameResolver: String? Function(String recipeId)?` — MealTile calls this per component_id to get a name or null (archived/unresolvable). When null, the tile renders just "(N recipes)" as a fallback (same as today's decorative badge text) — this is the backward-compat path so book-detail + search callers don't break.
  - Gains `isFavorited: bool` (default false) and `onFavoriteToggle: VoidCallback?` (optional — tile hides the star when null).
  - Gains `selected: bool` (default false). When true, renders a centered checkmark overlay over the collage using the same grammar as book-detail's `_RecipeCard` selected state.
- **"N recipes" decorative badge is retired.** Component chips carry both the count and the names (via `+N` suffix when >2). The collage hero is simpler without the badge; the "Meal" pill in the top-left is now the primary visual signal. If `componentNameResolver` is null (callers that haven't migrated yet), fall back to rendering "(N recipes)" in the chip-row position so no caller loses information.
- A favorite-star overlay renders in the top-right when `onFavoriteToggle != null`, matching RecipeCard's star position + icon + color treatment. Tap fires `onFavoriteToggle`. Callers (home grid) pass the current `is_favorite` from the `MealSummary` and wire the toggle to `favoriteMeal(id)` / `unfavoriteMeal(id)` with optimistic update + rollback on error.
- Widget tests: `meal_tile_v2_test.dart` covers 0/1/2/3/5-component chip rendering (with and without archived fallback), accent border present, Meal pill present with drop shadow, favorite star present + tap toggles + errors roll back, selected-state checkmark present. Separately covers the no-resolver-provided backward-compat path.
- Zero-regression: existing MealTile callers (book-detail grid, search results) do not pass `componentNameResolver` at first — they fall back to "(N recipes)." Follow-up PRs (not in this epic) can adopt the resolver for parity. Book-detail is allowed to pass `selected: _isSelectMode && _selectedRecipeIds.contains(...)` **if it chooses** — but that is a later follow-up; book-detail's current Meal-non-selectable behavior is preserved as-is by leaving `selected` at its default false.

**Out of scope:** selection mode, bulk bar, filter changes. This story ships on its own.

### Story hmp-2 — Home selection mode: long-press, selection app bar, tile selected-state

**Goal**: Wire the selection state machine + alternate AppBar + selected-state visuals, with the bulk bar present but every action disabled (it is made live in hmp-3 and hmp-4).

**Acceptance criteria:**

- New `HomeSelectionController` implemented as a **Riverpod `StateNotifier<HomeSelectionState>`** (matches the project convention — `HomeFilterState` and per-book recipe providers are all Riverpod today). The controller exposes methods `toggleRecipe(id)`, `toggleMeal(id)`, `enterWith(kind, id)`, `exit()`, plus computed getters `selectionShape` and `primaryAction`. Exposed via `homeSelectionProvider = StateNotifierProvider.autoDispose<HomeSelectionController, HomeSelectionState>(...)`. State machine covers every transition listed in the spec. `primaryAction` getter returns a sealed class (`CreateMealAction`, `AddToMealAction(Meal)`, `DisabledAction(String reason)`, `EmptyAction`) so the bulk bar pattern-matches cleanly instead of checking bools.
- `home_screen.dart` consumes the provider, swaps `AppBar` → `SelectionAppBar` when `state.isSelectMode`, passes `selected` props down to RecipeCard + MealTile.
- Long-press on a RecipeCard or MealTile enters selection mode (if not active) and toggles that item's ID in the appropriate set. Haptic tick fires on entry (`HapticFeedback.selectionClick`).
- Tap in selection mode toggles selection (does NOT navigate). Tap outside any tile does nothing (no accidental exit-on-background-tap in v1 — selection exit is via X or back gesture or successful bulk op).
- Tap X in the `SelectionAppBar` or system back gesture exits selection mode with sets emptied.
- **Bulk bar placement**: `home_bulk_action_bar.dart` is mounted in `Scaffold.bottomNavigationBar` slot when `state.isSelectMode`, not as a `Positioned` overlay. Rationale: home uses a `CustomScrollView` with slivers, and Positioned inside a Stack that contains slivers is fragile (doesn't respect SafeArea, can overlap FABs, gets clipped on some Android gesture-nav configurations). The existing home screen does not use bottomNavigationBar today, so the slot is free. When selection mode is off, the slot is null and no bar renders.
- In this story all bulk-bar buttons are **visually present but functionally stub** — `Create Meal` / `Add to "<name>"` / `Archive` each render with correct labels derived from `primaryAction`, but taps are logged (`developer.log('stub: bulk action <name>')`) and do not dispatch. Disabled states + tooltips are fully wired (they are presentational). Disabled tooltip copy per spec:
  - 1 recipe, 0 meals → "Select 1 more recipe to create a Meal, or select a Meal to add to"
  - 0 recipes, 1 meal → "Select recipes to add to this Meal"
  - 2+ meals, any recipes → "Select only one Meal at a time"
- Old `_showRecipeActions` sheet is **deleted** from home_screen.dart (per FR-HMP-1). Its call site (the recipe long-press handler) is replaced by the selection-mode entry.
- Widget tests: `home_selection_controller_test.dart`, `home_selection_mode_test.dart`, `home_bulk_action_bar_test.dart` (the disabled-state + tooltip copy subset) all pass.
- Zero-regression: with selection mode NOT active, home renders bit-identically to pre-epic. Widget test `home_zero_meal_regression_test.dart` confirms.

**Depends on:** hmp-1 (MealTile must accept `selected: bool`). Can be in-flight in parallel with hmp-4 (filters).

### Story hmp-3 — Bulk actions: Create Meal + Add to Meal + Archive wiring, partial-failure pattern

**Goal**: Make the bulk bar's three actions live, including the partial-failure snackbar + dialog pattern.

**Acceptance criteria:**

- **Create Meal** dispatch: opens `CreateMealSheet.show(...)` with `initialComponents` derived from selected recipe IDs (preserving selection order), `bookId` derived from the first-selected recipe's `recipeBookId`, `bookName` derived from the matching recipe book in the home's loaded state. Success closure exits selection mode, invalidates `mealsByBookProvider` for the target book + the home meal list, and reloads the grid. Cancel closure leaves selection mode intact so the user can adjust.
- **Add to Meal** dispatch:
  - Client-side dedup: filter selected recipe IDs against the target Meal's existing component recipe IDs (read from `_meals` in home state); if the resulting list is empty, show snackbar "All selected recipes are already in this Meal" and exit selection mode with no API calls.
  - Parallel dispatch: `Future.wait(recipeIds.map((rid) => addRecipeToMeal(mealId, rid)))` but collecting per-call results (success or error with typed reason) instead of using `eagerError`.
  - On all-success: snackbar "Added N recipes to <Meal Name>." Exit selection mode. Invalidate the Meal in provider cache + reload.
  - On partial failure: snackbar "Added X of Y — see details" with a View action that opens `BulkPartialFailureDialog` listing each failed recipe by name + one-line reason parsed from the typed exception. Selection clears on dialog dismiss.
  - On all-failure: snackbar "Could not add recipes — see details." Same dialog; selection clears on dismiss.
- **Archive** dispatch:
  - Confirmation dialog: "Archive {N} recipe(s) and {M} Meal(s)? You can restore them later from Archive." Two buttons: Cancel, Archive.
  - On confirm: parallel dispatch `bulkArchiveRecipes(recipeIds)` + `Future.wait(mealIds.map(archiveMeal))`. Collect per-call results; any Meal archive failure is individually reported.
  - Partial-failure pattern identical to Add-to-Meal. Success closure invalidates home list + reloads.
- `BulkPartialFailureDialog` widget implemented. Accepts `{operation: 'add-to-meal' | 'archive', results: List<BulkOperationResult>}`. Renders a `ListView` of one row per failed item with `displayName` + `errorReason`. One dismiss button.
- Widget tests: `home_bulk_add_to_meal_test.dart`, `home_bulk_create_meal_test.dart`, `home_bulk_archive_test.dart` cover every acceptance bullet plus the dedup / all-fail / confirm-cancel branches.

**Depends on:** hmp-2 (bulk bar scaffold). Does NOT block hmp-4 (filters).

### Story hmp-4 — Home filter extensions: Show type + Hide components of Meals

**Goal**: Two new client-side filter axes in the existing `FilterBottomSheet`, wired through `HomeFilterState` into `home_screen.dart`'s `_applyFilters`.

**Acceptance criteria:**

- `HomeFilterState` extended with `showType: ShowTypeFilter` (enum values `all | recipesOnly | mealsOnly`, default `all`) and `hideComponentsOfMeals: bool` (default `false`).
- `FilterBottomSheet` renders:
  - A new **Show** section between **Sort by** and **Meals**. Renders three single-select `FilterChip`s: "All" / "Recipes only" / "Meals only." Chip state is radio-style (selecting one deselects the others).
  - A new **Hide components of Meals** toggle row immediately below the Show section. `SwitchListTile` (or equivalent) with title and muted subtitle "Hide recipes that are part of any Meal." Positioned above the **Meals** section.
- Both new fields emit through `onApply(HomeFilterState state)`.
- `home_screen.dart` `_applyFilters` applies the two new filters client-side in this order: first `showType` (if `recipesOnly` or `mealsOnly`, filter out the wrong kind), then `hideComponentsOfMeals` (compute `componentIds` from in-memory Meals, filter recipes whose `id` is in that set — Meals are never filtered by this toggle).
- Active-dot pill: the existing "any non-default filter" computation is extended to include `showType != all || hideComponentsOfMeals == true`.
- "Clear all" snackbar / reset path resets both new fields to defaults alongside the existing sort/meal/vibe resets.
- Widget tests: `filter_bottom_sheet_show_type_test.dart` + `home_filter_hide_components_test.dart` cover: every Show-chip toggle effect on the grid; Hide-components with 0 Meals is a no-op; Hide-components with 1 Meal (3 components) hides all 3 recipes; Meals are never hidden by this filter; active-dot reflects state correctly.

**Depends on:** nothing in this epic (independent). Can ship in parallel with hmp-2 / hmp-3. Recommended merge order: hmp-1 → hmp-4 → hmp-2 → hmp-3.

### Story hmp-5 — Regression sweep: zero-Meal parity, selection + filter interaction, a11y pass

**Goal**: The load-bearing zero-regression guarantee, plus the cross-cutting scenarios the per-story tests don't naturally cover, plus an accessibility sanity pass.

**Acceptance criteria:**

- `home_zero_meal_regression_test.dart` (added in hmp-2, extended here) renders a zero-Meal fixture and asserts:
  - Grid contains only RecipeCard instances (no MealTile in the tree).
  - Filter sheet's two new rows are present but functionally no-op (Show: Meals only shows empty grid with empty state; Hide components toggle has no visible effect).
  - Long-press still enters selection mode; bulk bar primary is disabled with correct tooltip at 1R, enabled (Create Meal) at 2R+.
  - Old `_showRecipeActions` sheet is NOT summoned (the code path is gone).
- **Selection + filter interaction** test: enter selection mode, select 2 recipes, flip "Meals only" filter — grid hides both recipes but selection set retains both IDs; bulk bar primary still reflects Create Meal enabled. Flip back — recipes reappear with selection intact.
- **Selection + refresh interaction** test: select 1 Meal + 2 recipes; simulate background refresh that removes the Meal from the list (e.g., archived elsewhere). Meal ID silently drops from selection set; if selection is still non-empty (≥1 recipe), selection mode stays on and bulk bar primary recomputes. If selection becomes empty, selection mode exits with "Selection cleared — content changed" snackbar.
- **A11y pass** (small scope — not a full audit): Semantics labels on SelectionAppBar's X button ("Exit selection"), on bulk bar primary button (dynamic text — "Create Meal" / "Add to <Meal Name>" / disabled reason), on bulk bar Archive button ("Archive selected"), on MealTile v2's "Meal" pill ("Meal, N recipes"), on MealTile's favorite star ("Favorite" / "Unfavorite"). Widget test asserts each.
- **Epic-wide widget-test smoke**: add a single widget test that walks the full primary happy path — long-press, tap, Create Meal, verify new Meal appears in grid. Another for long-press Meal + recipe, Add to Meal, verify component chips update. A third for the filter path.
- **End-to-end integration test** (new requirement per QA-lens party-mode): one integration test (`app/integration_test/meals_home_promotion_flow_test.dart`) that spins up the app against a test fixture backend, exercises the full long-press → Create Meal flow on the home grid, then fetches the created Meal via `getMeal(id)` and asserts the returned components match the selected recipes. This is the one surface where real API + real widget together matter — widget tests alone can't catch a contract drift in `CreateMealSheet`'s submission payload.
- Manual QA walkthrough checklist committed to the story output file AND to the QA walkthrough standalone file (per MEMORY.md feedback — QA walkthrough is required on story completion).

**Depends on:** hmp-1 through hmp-4 all merged.

## Dependencies

- **Blocks**: nothing.
- **Depends on** (already shipped, no new work):
  - `epic-meals-create-and-view` — CreateMealSheet + MealTile + Meal model + archive/restore/favorite endpoints.
  - `epic-meals-discoverability` — home grid Meal merge + listMeals(scope=home).
  - Existing `POST /v1/recipes/bulk/archive`.
- **Parallelizable with**:
  - `epic-meals-sharing-and-ai` (backlog) — completely independent; touches Meal detail + share endpoints, not home.
  - `epic-bugs-home-polish` (backlog) — soft overlap on `home_screen.dart`; home-polish-2 (post-add-recipe nav) does not touch selection-mode code paths, but the two epics' merges should be sequenced to avoid conflict-resolution churn. Recommend shipping this epic AFTER home-polish lands, OR coordinating merge order; party-mode to discuss.
  - `epic-cook-mode-polish` / `epic-cook-mode-timers` — fully independent.
- **Conflicts with**: none.

## Resolved Questions (party-mode 2026-04-20)

All pre-workshop questions are resolved. Decisions carried forward:

- **Q1 — "Add to Meal" single-recipe variant** → **Deferred**. Recipe detail's overflow menu gaining an "Add to Meal…" item is a valid follow-up but not in this epic. For v1, the user must include the target Meal in the home selection. Rationale: keeps the multi-select model coherent (selection is the anchor) and avoids introducing a Meal-picker sheet flow that duplicates the selection semantics.
- **Q2 — Selection persistence across filter changes** → **Keep selection**. Selection is a set of IDs; rendering is orthogonal. If a filter toggle hides a selected item, the ID stays in the set. Matches iOS Photos + Gmail mental models. Toggling the filter back re-reveals the selected item.
- **Q3 — Bulk-archive-meals endpoint** → **Client-iterate for v1**. N is small (≤5 realistically), each call is cheap, partial-failure semantics are already shared with the recipe path. If dogfood data shows Meal-archive is a common flow, spawn a backend follow-up with a `POST /v1/meals/bulk/archive` endpoint — but not in this epic.
- **Q4 — Partial-failure dialog shape** → **Ship the dialog**. Per-item list with reasons. Cheap to build, informative to use. The snackbar-only alternative was considered and rejected (users want to know which items failed).
- **Q5 — Haptic on long-press entry** → **Ship in home with `HapticFeedback.selectionClick`**. Book-detail multi-select does not currently emit haptic on selection-mode entry; a follow-up ticket to add it in book-detail for consistency is out of scope here.
- **Q6 — MealTile accent border token** → **Read `theme.dart` during hmp-1**. If a Meal-accent token exists, reuse. Otherwise introduce a `MealAccent` token in this epic (theme change, not backend). hmp-1 AC captures this.
- **Q7 — Merge ordering with `epic-bugs-home-polish`** → **Race, resolve at merge**. The home-polish epic's `home-polish-2-post-add-recipe-nav` does not touch selection-mode code paths; conflict-resolution on `home_screen.dart` is manageable.

## Open Questions

**None for the user.** Party-mode resolved all pre-workshop questions above. The one remaining implementation-time decision (reuse vs. introduce `MealAccent` token) is an ergonomic call inside hmp-1, not a user-facing choice.

**Carrying forward to sibling epics:**

- **To `epic-bugs-home-polish`**: both epics modify `home_screen.dart`. Whichever lands first, the second author should rebase onto the first. No deep conflict expected — home-polish-2's post-create nav sits in the CreateRecipeSheet success handler path; this epic's selection-mode wiring is structurally separate.
- **To a future "Add to Meal from recipe detail" follow-up** (Q1 deferral): when/if that ships, reuse the `BulkPartialFailureDialog` pattern introduced here (single recipe_id call doesn't strictly need it, but the shared widget keeps the Meal-add ergonomics uniform).
- **To any future epic that touches MealTile**: the `componentNameResolver` backward-compat path (renders "(N recipes)" when resolver is null) means existing non-home callers don't need to migrate on day one. A follow-up can land the resolver on book-detail + search-results surfaces for chip-row parity without being blocked by this epic.
