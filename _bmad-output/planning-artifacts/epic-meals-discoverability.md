<!-- refined via party-mode 2026-04-18 -->
# Epic: Meals — Discoverability (home, search, favorites, archive, reverse-lookup)

## Overview

`epic-meals-create-and-view` (foundation) shipped Meals as a first-class entity inside a recipe book. Meals appear in the book detail grid, have their own detail + edit screens, and the `meal_favorites` table + `POST/DELETE /v1/meals/{id}/favorite` endpoints are **already wired live in foundation**. This follow-on epic surfaces Meals on every OTHER recipe surface the user already uses — the home screen, global search, favorites section, archive view — and adds a **"Used in these Meals"** row on the recipe detail screen so a user browsing Lemon Dressing discovers it is part of the Kale Salad Meal.

**Goal.** When this epic ships, a user can:

1. Find a Meal via search by typing either its own name ("Kale Salad Meal") OR any component recipe's name ("dressing" → Kale Salad Meal appears because its component is Lemon Dressing). **This component-name search is the killer feature** — without it, Meals feel like a second-class concept the user has to memorize by name.
2. See Meals in the home grid alongside recipes, with a **MealTile** widget (separate widget, not an extended RecipeCard) carrying a decorative "N recipes" badge.
3. See Meals in the favorites carousel on home when they have favorited any Meal.
4. See archived Meals in the archive view, same list as archived recipes, restored via the `POST /v1/meals/{id}/restore` path foundation already ships.
5. On any recipe detail screen, see a **"Used in these Meals"** horizontal row listing the Meals that include that recipe. Empty → section is hidden entirely.

**Day-1 zero-regression bar — LOAD-BEARING.** A user with **zero Meals in any book they can read** must see pixel-identical behavior to today on every surface touched: home grid, search results, favorites section, archive view, and recipe detail screen. No empty "Meals" section, no empty "Used in these Meals" header, no shift in sort order, no extra loading spinner. Widget tests for each surface MUST include a zero-Meal fixture and a visual-diff-equivalent assertion against the pre-epic render.

**Scope boundary.** This epic does NOT introduce a Meal-favorites migration or handlers — those land in foundation. It does NOT touch `meal_events`, sharing (`share_token` public endpoints), MCP tools, or AI pairing. It does NOT add a dedicated "Meals" tab — Meals belong where recipes belong.

## End-User Flow

1. **Home screen.** Leo opens the app. The home grid is a single `GridView.count` as it is today. Today it renders `RecipeCard` for every cell; after this epic it renders `RecipeCard` for recipes and `MealTile` for meals in the same grid, sorted by a single `updated_at DESC` merge of both streams. The favorites section (horizontal carousel above the grid) likewise contains both favorited recipes and favorited Meals, rendered inline. If Leo has zero Meals, the grid renders **only** `RecipeCard` tiles — identical to today.
2. **Search.** Leo taps the search bar, types "dressing." The search hits `GET /v1/search?q=dressing&scope=recipes,meals` (comma-list scope — decided below). The response gains a new **`my_meals`** array sibling to `my_recipes`. Results render in the existing sectioned layout: **My Recipes**, **My Meals**, **Public Recipes**, **People**. Within the My Meals section: exact-name Meal matches rank first, component-name matches below, with a muted sublabel on component-matched Meals reading **"Matches: Lemon Dressing"** so the user understands why the Meal appeared.
3. **Recipe detail → "Used in these Meals."** Leo taps into Lemon Dressing (a single recipe). Below the ingredients section and above the notes section, a new widget fires `GET /v1/recipes/{id}/meals`. If the response is non-empty, a horizontal `ListView` row appears with the section header **"Used in 1 meal"** (or "Used in N meals"), showing MealTile-sized cards (see Frontend § sizing). Empty → the section is not rendered at all.
4. **Favorites on home.** Leo favorited Kale Salad Meal on the Meal detail screen yesterday (foundation epic wired this). The home favorites carousel now includes it alongside favorited recipes. Tapping opens `/meals/:id`.
5. **Archive view.** Leo archived the Kale Salad Meal. The archive view (`archived_recipes_screen.dart`) lists both archived recipes and archived Meals, sorted together by `archived_at DESC`. Restore for Meals uses `POST /v1/meals/{id}/restore` (foundation).

**What does not change.** Search input, filter chips, sort options, the single-recipe tile, empty states on zero-recipe cold-start, the header/nav. The recipe detail layout above the new "Used in these Meals" section is untouched.

**Public recipe pages: hide "Used in these Meals"** (was an open question; decided below).

## Frontend Changes

Touches `app/lib/features/home/`, `app/lib/features/search/`, `app/lib/features/recipes/`, and `app/lib/features/meals/` (foundation introduced this dir).

### Home grid: two streams, single merge (Frontend-dev decision)

`home_screen.dart` today calls `getRecipeBooks()` then for each book `getRecipeBook(id)` to pull recipes. To surface Meals:

- Add a parallel `_apiClient.getMeals(scope: 'home')` call (`GET /v1/meals?scope=home`) fired alongside the recipe fetch inside the existing `Future.wait` at `_loadRecipes`.
- Merge the two lists into a single `List<dynamic>` of mixed items distinguished by a `kind` key (`'recipe'` or `'meal'`) the frontend tags locally.
- Sort by `updated_at DESC` across the union.
- `_buildRecipeGrid`'s itemBuilder becomes: `item.kind == 'meal' ? MealTile(...) : RecipeCard(...)`. Both widgets share the same `childAspectRatio: 0.7` so the grid stays regular.
- Favorites section: extend the existing `/v1/favorites` response to include `favorited_meals` (backend story md-3 below). Flutter iterates both arrays and builds tiles with the same shared 120px-wide horizontal card.
- **Zero-Meal user**: the merge of an empty `meals` list with the existing recipes list is a no-op. The itemBuilder never hits the `'meal'` branch. Render is bit-identical.

### Search: polymorphic server response, sectioned client render (Frontend-dev decision)

The backend extends `GET /v1/search` to add a `my_meals: list[MealSearchResult]` key alongside the existing `my_recipes`. Flutter's `search_screen.dart` parses it into a new `_myMeals` list field and renders a new **"My Meals"** section between "My Recipes" and "Public Recipes" using the existing `_buildSectionHeader` + list-tile pattern. Each Meal result renders as a tile that visually parallels the existing recipe tile (100px square image — replaced by the 2/3/4-up collage thumbnail set rendered inline — title, subtitle, chevron) but carries:

- "N recipes" decorative badge on the image.
- If the hit was a component-name match: a muted third subtitle line reading **"Matches: <component_name>"** using the matched component's name from the response payload (backend returns a `matched_component` field on component-matches; null on direct name matches).

**Why sectioned, not inline.** Mixing Meals into `my_recipes` would require client-side type discrimination in every iteration site and would silently break any caller that does `response['my_recipes'].map(...)`. A separate key is a strictly-additive schema change: old clients ignore it, new clients render it. It also lets the section header signal "these are meals" without mucking with per-tile chrome.

**Scope parameter** sent by the client: `scope=recipes,meals` — comma list. The existing server code already uses `scope == "recipes"` as a gate; we add a parallel `"meals" in scope_list` gate. Old clients that send `scope=recipes` (only) continue to get meal-less results. New clients send `scope=recipes,meals`. Unknown scope values continue to fall back to "everything" (existing server behavior — preserve).

### "Used in these Meals" widget (Frontend-dev sizing decision)

New widget `meals_using_this_recipe.dart` in `app/lib/features/recipes/widgets/`:

- **Section header**: "Used in 1 meal" / "Used in N meals" (textTheme.titleMedium, same weight as existing recipe-detail section headers).
- **Horizontal row**: `ListView.separated(scrollDirection: Axis.horizontal)`, fixed `height: 130`. Each card is **140×120** (width × height of image, + ~10px for name underneath, total 130). Renders the collage hero (1/2/3/4-up via the foundation `ComponentCollageHero` at a small scale) + Meal name single-line ellipsis + "N recipes" decorative badge bottom-right.
- **8+ items**: the horizontal list scrolls — no explicit "See all" affordance in v1. The user can scroll. If UX testing shows a preference for a "See all" overflow at >N, add in a follow-up.
- **Loading state**: three 140×120 `ShimmerCard` placeholders while the fetch is in flight.
- **Empty state**: widget returns `SizedBox.shrink()` — **the entire section including its header does not render**. This is critical for zero-regression: a user who has no Meals sees no change to recipe detail.
- **Error state**: widget returns `SizedBox.shrink()` on fetch failure. A failed "Used in these Meals" must never block recipe detail from rendering. Error is logged to `error_reporter`.
- **Public recipe pages** (`public_recipe_screen.dart`): do NOT mount this widget. See Design Principles § Public page decision.

### MealTile — already exists (foundation delivered it)

Foundation's `app/lib/features/meals/widgets/meal_tile.dart` already ships the MealTile widget with the collage hero, decorative "N recipes" badge, and whole-tile tap-to-open. This epic reuses it on home grid, search results, favorites carousel, and archive. **Do not leak Meal shape into `_RecipeCard`.**

### Search results: reuse or new tile?

Home grid reuses `MealTile` directly. Search results use a **new `meal_search_tile.dart`** widget in `app/lib/features/search/widgets/` because the search tile is a horizontal ListTile-style row (100px square image + title + subtitle), not a grid card. This mirrors the existing `_buildRecipeTile` helper in `search_screen.dart`. The two widgets (MealTile for grid, MealSearchTile for list row) share no code intentionally — each is monolithic.

### Archive view

Extend `archived_recipes_screen.dart`. Today it calls an archived-recipes endpoint and renders a list. Add a parallel `getArchivedMeals()` call (`GET /v1/meals?archived=true`), merge both into one list sorted by `archived_at DESC`, itemBuilder switches on `kind` and renders `MealTile` in a grid cell or a `ListTile`-equivalent (whichever the current archive screen uses). Restore path for Meals hits `POST /v1/meals/{id}/restore`.

### File list

- **`app/lib/features/home/home_screen.dart`** (MODIFY) — parallel meal fetch via `getMeals(scope: 'home')`; merge into `_recipes` list as mixed `kind`-tagged items; itemBuilder switches `MealTile` vs `RecipeCard`; favorites section iterates both arrays from extended `/v1/favorites` response.
- **`app/lib/features/search/search_screen.dart`** (MODIFY) — adds `_myMeals` state field, parses new `my_meals` key from response, renders new "My Meals" section between "My Recipes" and "Public Recipes," sends `scope=recipes,meals`.
- **`app/lib/features/search/widgets/meal_search_tile.dart`** (NEW) — horizontal list-row tile for a Meal in search results, shows collage + name + optional "Matches: <component>" subtitle + book name + decorative badge.
- **`app/lib/features/recipes/recipe_detail_screen.dart`** (MODIFY) — inserts `MealsUsingThisRecipe` widget between the ingredients section and notes section.
- **`app/lib/features/recipes/widgets/meals_using_this_recipe.dart`** (NEW) — horizontal-scroll row of MealTile-sized cards, hides entirely on empty/error, shimmer on load.
- **`app/lib/features/recipes/archived_recipes_screen.dart`** (MODIFY) — merges archived recipes + archived meals, sorted by `archived_at DESC`, itemBuilder switches by `kind`.
- **`app/lib/core/services/api_client.dart`** (MODIFY) — adds `getMeals({String? scope, bool archived = false})` and `getMealsUsingRecipe(String recipeId)` typed wrappers; extends `search` to send `scope=recipes,meals` by default from the search screen caller.

### Widget tests (non-negotiable)

- `home_screen_meals_test.dart`:
  - **Zero-Meal fixture**: grid renders N recipes identically to today. No MealTile in tree. No empty Meals section.
  - **Mixed fixture**: grid renders interleaved MealTiles + RecipeCards sorted by `updated_at`.
  - **Meals-only fixture**: grid renders only MealTiles.
  - Favorites carousel: favorited meals appear alongside favorited recipes in the same strip.
- `search_screen_meals_test.dart`:
  - **Zero-Meal fixture**: no "My Meals" section rendered (zero-regression).
  - **Direct name match**: Meal hit in "My Meals" section, no "Matches:" subtitle.
  - **Component-name match**: Meal hit renders "Matches: Lemon Dressing" subtitle.
  - **Mixed**: Recipe hits and Meal hits both render, in correct section order.
  - Scope parameter: wrappers assert `scope=recipes,meals` is sent.
- `meals_using_this_recipe_test.dart`:
  - **Zero meals referencing this recipe**: widget returns `SizedBox.shrink()`; recipe detail rendering is bit-identical to today.
  - **1 meal**: section header reads "Used in 1 meal"; one card rendered.
  - **5 meals**: horizontal scroll works; all 5 cards present.
  - Tap card → `context.push('/meals/:id')`.
  - Fetch error → section hidden, no user-facing error.
- `archived_recipes_meals_test.dart`: zero-meal regression; mixed archive; restore wired to `POST /v1/meals/{id}/restore`.

## Backend Changes

Small surface: extend `GET /v1/search`, add `GET /v1/recipes/{id}/meals`, extend `GET /v1/meals` with `scope=home` + `archived` params, extend `GET /v1/favorites` to include favorited meals.

### `services/api/src/api/v1/search/unified_search.py` (MODIFY)

Extend the `UnifiedSearch` endpoint:

- **Scope parsing**: replace the existing `recipes_only = scope == "recipes"` gate with a scope-set parser: `scope_set = set(scope.split(",")) if scope else None`. If `scope_set is None`: preserve today's everything-behavior (backward-compat). If `scope_set == {"recipes"}`: recipes only, no users, no meals (matches today's `scope=recipes`). If `"meals" in scope_set`: include meals in the response. If `"meals"` is the only scope: skip recipe + user tiers.
- **New tier: `_search_my_meals(query, limit, user, book_ids)`** — exact-match tier only in v1 (no fuzzy / semantic tiers for meals). Uses existing `RecipeBookUser` for access control. Predicate:
  - `meals.name ILIKE '%query%'` OR `meals.description ILIKE '%query%'` (direct match) — priority rank 0.
  - `EXISTS (SELECT 1 FROM meal_recipes mr JOIN recipes r ON r.id = mr.recipe_id WHERE mr.meal_id = meals.id AND r.name ILIKE '%query%')` (component-name match) — priority rank 1.
  - `archived_at IS NULL`, `recipe_book_id IN (user's readable book ids)` — authorization.
  - `ORDER BY priority_rank, meals.name ILIKE :query DESC, meals.updated_at DESC LIMIT :limit`.
  - `selectinload(Meal.components).selectinload(MealRecipe.recipe)` for hydration (mirrors foundation's read pattern).
  - For component-name hits, identify the **specific** matched component per Meal via a correlated subquery result so the response can return `matched_component: {recipe_id, name}`. For direct-name hits, `matched_component: null`.
- **Response schema extension**: add `my_meals: list[MealSearchResult]` where
  - `MealSearchResult { id, name, description, recipe_book_id, recipe_book_name, component_count, top_component_image_urls (≤4), matched_component: {recipe_id, name} | null }`.
- **Pagination across union**: union-paging is NOT attempted in v1. Each tier takes its own `limit` (existing pattern). The client already handles three independent arrays (`my_recipes`, `public_recipes`, `users`) — add `my_meals` as a fourth. Per-section limit is still 20 default, 50 max — **no cross-type ranking**. This keeps the ORDER BY concern local to each tier and avoids the tricky ranking problem of scoring a Recipe match against a Meal match on the same axis.
- **Auth**: reuse the `_get_my_book_ids(user)` helper for the meal tier. A Meal is visible iff its `recipe_book_id` is in the user's readable book set. **Component-name matches surface Meals from any readable book, including Meals whose matched component lives in a different (also-readable) book** — this is the locked decision from foundation: components can come from any book the user can read, so the reverse — finding the Meal by the component — must inherit the same visibility rule.
- **No new indexes** — the `meals(recipe_book_id)` index from foundation + the `meal_recipes(recipe_id)` secondary index from foundation (for the reverse-lookup predicate) cover this query. The `meals.name` / `meals.description` ILIKE scans are bounded by the book-id IN clause and do not require GIN indexes in v1. If search latency degrades at scale (target: p95 <300ms on 1k Meals per user), add a GIN trigram index in a follow-up; explicitly out of scope for this epic.

### `services/api/src/api/v1/recipes/list_meals_using_recipe.py` (NEW)

`GET /v1/recipes/{recipe_id}/meals` — reverse lookup.

- **Auth**: 403 if the user can't read the recipe. 404 if the recipe does not exist. (If the recipe is archived, returns the list but still authorized — archived recipes are still readable.)
- **Query**: `SELECT m.* FROM meals m JOIN meal_recipes mr ON mr.meal_id = m.id WHERE mr.recipe_id = :recipe_id AND m.archived_at IS NULL AND m.recipe_book_id IN (user's readable book ids)`.
  - Per locked context: **Meals whose book the user can read are returned, even if the Meal's book differs from the recipe's book**. If Leo can read Recipe X (in book A) AND he can read Book B, and someone in Book B created a Meal that includes Recipe X, Leo sees that Meal in his reverse-lookup response. This makes "Used in these Meals" a true cross-book discovery surface.
- **Pagination**: default limit 20, max 50. No cursor in v1 — the realistic cap (a single recipe referenced in dozens of Meals) is an edge case.
- **Response**: `list[MealSummaryResponse]` — reuses the schema foundation defined (`id, name, component_count, top 4 component image_urls, recipe_book_name, updated_at`).
- **N+1 prevention**: single query joins `meals` to `meal_recipes` for the predicate, then a separate selectinload for each returned Meal's components (standard foundation pattern). Two queries total regardless of result count.
- **Register in `services/api/src/routers/v1/recipe_router.py`** (MODIFY) — add `@recipe_router.get("/{recipe_id}/meals")` handler.

### `services/api/src/api/v1/meals/list_meals.py` (MODIFY — from foundation)

Foundation already ships `GET /v1/meals` (paginated, excludes archived). Extend filter params:

- `?archived=true|false` — when `true`, returns only archived Meals (for archive view). When `false` or absent, excludes archived (today's behavior).
- `?scope=home` — returns Meals optimized for home grid: exclude archived, sort by `updated_at DESC`, paginate default 30 items. This is a hint, not a distinct endpoint — it just sets defaults.
- `?in_books=<id1>,<id2>` — **not added in v1**. The home grid fetches across all readable books by default. Defer until a real use case appears.

### `services/api/src/api/v1/user/list_favorites.py` (MODIFY — or wherever `/v1/favorites` lives)

Extend the favorites GET response to include a `favorited_meals: list[MealSummaryResponse]` key alongside the existing `favorited_recipes` (or equivalent). Read from the `meal_favorites` table foundation created. The existing `items` key stays; add `favorited_meals` as an additive key. Old clients ignore it; new clients iterate both arrays for the favorites carousel.

### Tests (`services/api/tests/`)

- **`test_unified_search_with_meals.py`** (NEW):
  - Direct Meal-name match returns Meal with `matched_component=null`.
  - Component-name match returns Meal with `matched_component={recipe_id, name}`.
  - Meal name + component both match same query — direct match ranks first; no duplicate Meal in response.
  - Auth: Meal in a book the user cannot read is excluded.
  - Cross-book component visibility: user reads Book A AND Book B; a Meal in Book B references a recipe in Book A — the Meal surfaces on a component-name search of the recipe's name. (This is the locked-context assertion.)
  - `scope=recipes` (old client) returns zero Meals.
  - `scope=recipes,meals` returns Meals.
  - `scope=meals` returns Meals only (no recipes, no users).
  - **Zero-Meal database**: search returns `my_meals: []`, `my_recipes: [...]`, identical to the recipe-only response shape modulo the new empty key.
  - Archived Meals are excluded from search results.
  - Pagination: `limit=5` returns at most 5 Meals in `my_meals`; per-tier limit independent of other tiers.
- **`test_list_meals_using_recipe.py`** (NEW):
  - Happy: recipe referenced by 3 Meals → returns all 3.
  - Empty: recipe referenced by 0 Meals → returns `[]`, not 404.
  - Auth fail on recipe: 403.
  - 404 on nonexistent recipe.
  - Cross-book visibility assertion.
  - Archived Meals excluded.
- **`test_list_meals_filters.py`** (NEW or extension of foundation's `test_meal_router.py`):
  - `archived=true` returns only archived, sorted by `archived_at DESC`.
  - `archived=false` (default) excludes archived.
  - `scope=home` — default pagination + sort.
- **`test_favorites_with_meals.py`** (MODIFY existing favorites test): GET `/v1/favorites` includes `favorited_meals` when user has favorited Meals; empty array when none.
- **Coverage**: 100% branch on every new handler and every new branch in `unified_search.py`. The `coverage.xml` CI gate from CLAUDE.md is non-negotiable.

## Infrastructure Changes

**None.**

- No new tables. `meal_favorites` already exists from foundation.
- No new indexes. Foundation's `meal_recipes(recipe_id)` secondary index covers the reverse-lookup query. `meals(recipe_book_id)` covers the search-authorization predicate. `meal_recipes` PK `(meal_id, recipe_id)` covers the component-match EXISTS predicate.
- No new AWS resources, no new env vars, no Dockerfile changes.
- Standard deploy: `npx nx run api:docker-build`, standard ECS rolling task swap. No migrator run required (no schema changes).
- Search performance: existing `ILIKE '%q%'` against `meals.name` is not-indexable but bounded by the book-id IN clause — for any single user the scan is over ≤ their Meal count per readable book. Realistic cap: low hundreds. If p95 exceeds 300ms at dogfood scale, add a GIN trigram index on `meals.name` in a follow-up; not blocking this epic.
- Fixture strategy: add a `meals_seed.sql` to `seeds/` for integration tests with (a) zero-Meal user fixture, (b) mixed user fixture, (c) Meals-only user fixture, and (d) cross-book-component fixture (user reads two books; a Meal in book B references a recipe in book A). These drive the widget test seeds AND the API test seeds.

## Design Principles

1. **Day-1 zero-regression is LOAD-BEARING.** Every touched surface must render bit-identically for a zero-Meal user. Empty Meal sections render `SizedBox.shrink()`, not headers with "No meals yet" copy. Widget tests assert this explicitly.
2. **Component-name search is the killer feature.** Typing "dressing" finding Kale Salad Meal is the reason this epic exists. If that doesn't work end-to-end at ship, the epic has failed its primary user-value goal regardless of other progress.
3. **MealTile is a separate widget, not an extended RecipeCard.** Locked from foundation. This epic reuses foundation's `meal_tile.dart` directly and does NOT modify `_RecipeCard`. Each tile type stays monolithic.
4. **Decorative badge, single tap target.** The "N recipes" badge is never tappable. The whole tile opens the Meal. Locked from foundation.
5. **Sectioned search, not inlined.** Meals get their own "My Meals" section header in search results. This makes the type of each hit visually obvious and preserves the existing client parsing shape (`my_recipes` stays a flat list). Mixing Meals into `my_recipes` inline would be type-unsafe on the wire.
6. **Component-match visibility shows why a Meal matched.** A muted "Matches: <component_name>" subtitle on component-matched Meal hits. Direct-name matches omit this. Users who type ingredient-y strings understand instantly why a Meal they'd never named "dressing" is in the results.
7. **"Used in these Meals" hides entirely when empty.** No header, no empty state, no shimmer after fetch completes. This is the recipe-detail zero-regression guarantee.
8. **"Used in these Meals" does NOT appear on public recipe pages.** Leaking private Meal structure (even Meal names) to unauthenticated viewers of a public-shared recipe is a privacy regression. Public viewers see the recipe and no cross-reference. If a user wants to share a Meal publicly, they'll do so via the Meal's own `share_token` (sharing epic). `public_recipe_screen.dart` is explicitly NOT modified in this epic.
9. **selectinload everywhere.** Locked from foundation. Component hydration on search hits + reverse-lookup results uses `selectinload(Meal.components).selectinload(MealRecipe.recipe)`. No joinedload — the row-duplication cost is quadratic.
10. **No Meals tab.** Meals live where recipes live. A dedicated tab would signal that Meals are a distinct kind of thing the user must navigate to, which contradicts the foundational product thesis.
11. **No cross-type search ranking.** Recipes and Meals each rank within their own tier. We do not attempt a unified relevance score across two entity types in v1 — the ranking heuristics are different enough (component-match vs. ingredient-match vs. tag-match) that a single axis would produce wrong answers.
12. **Parallel `meal_favorites` table, no polymorphism.** Locked from foundation. This epic reads from the existing table — no schema work.
13. **API coverage pinned at 100%.** CI gate inherited from CLAUDE.md. Any uncovered branch in a new handler fails the build.

## File Structure

```
app/lib/features/home/
  home_screen.dart                              [MODIFY]  parallel meal fetch, merge, mixed itemBuilder

app/lib/features/search/
  search_screen.dart                            [MODIFY]  parse my_meals, render My Meals section
  widgets/
    meal_search_tile.dart                       [NEW]     horizontal list-row Meal tile for search

app/lib/features/recipes/
  recipe_detail_screen.dart                    [MODIFY]  +MealsUsingThisRecipe widget below ingredients
  archived_recipes_screen.dart                 [MODIFY]  merge archived meals + recipes
  widgets/
    meals_using_this_recipe.dart               [NEW]     horizontal scroll row, hides on empty
  public_recipe_screen.dart                    [NOT modified — privacy decision]

app/lib/core/services/
  api_client.dart                              [MODIFY]  getMeals(scope/archived), getMealsUsingRecipe, search scope default

services/api/src/api/v1/search/
  unified_search.py                            [MODIFY]  +_search_my_meals tier, +MealSearchResult,
                                                         +scope-set parsing

services/api/src/api/v1/recipes/
  list_meals_using_recipe.py                   [NEW]     GET /v1/recipes/{id}/meals

services/api/src/api/v1/meals/
  list_meals.py                                [MODIFY]  +?archived=true, +?scope=home

services/api/src/api/v1/user/
  list_favorites.py                            [MODIFY]  +favorited_meals key in response
  (or wherever /v1/favorites currently lives)

services/api/src/routers/v1/
  recipe_router.py                             [MODIFY]  +GET /{id}/meals

services/api/tests/
  test_unified_search_with_meals.py            [NEW]
  test_list_meals_using_recipe.py              [NEW]
  test_list_meals_filters.py                   [NEW]
  test_favorites_with_meals.py                 [MODIFY]

seeds/
  meals_seed.sql                               [NEW]     test fixtures for zero/mixed/meals-only + cross-book
```

## Stories

### Story md-1 — Backend: unified search extended with Meal matching

**Acceptance criteria:**

- `GET /v1/search` accepts `scope=recipes,meals` (comma-separated scope set). `scope=recipes` (old-client behavior) continues to exclude Meals. `scope=meals` returns Meals only. Absent scope returns everything (backward-compat).
- Response gains `my_meals: list[MealSearchResult]` alongside existing `my_recipes`, `public_recipes`, `users`. Each `MealSearchResult`: `{id, name, description, recipe_book_id, recipe_book_name, component_count, top_component_image_urls (≤4), matched_component: {recipe_id, name} | null}`.
- Match predicate: Meal matches iff `name` ILIKE or `description` ILIKE (direct match, `matched_component=null`) OR any component recipe's `name` ILIKE (component match, `matched_component` populated with the specific matched recipe).
- Ranking within `my_meals`: direct-name matches rank before component-name matches; within each rank, ORDER BY `updated_at DESC`.
- Auth: only Meals in books the user can read appear. Cross-book component visibility holds (test case asserts this).
- Archived Meals excluded.
- Per-tier `limit` (default 20, max 50). No cross-type ranking.
- `selectinload(Meal.components).selectinload(MealRecipe.recipe)` hydration.
- **100% branch coverage** on the new tier and the scope-set parser. Zero-Meal-user regression test confirms `my_recipes` ordering and contents are unchanged from pre-epic baseline.

### Story md-2 — Backend: reverse-lookup endpoint `GET /v1/recipes/{recipe_id}/meals`

**Acceptance criteria:**

- New handler `services/api/src/api/v1/recipes/list_meals_using_recipe.py`. Registered in `recipe_router.py` as `@recipe_router.get("/{recipe_id}/meals")`.
- Returns `list[MealSummaryResponse]` (foundation's schema — reuse).
- Empty list on no references (not 404).
- 403 if user can't read the recipe. 404 if the recipe does not exist.
- Cross-book: returns Meals from any book the user can read, not just the recipe's book.
- Archived Meals excluded. Archived recipes are still queryable (you may have archived Dressing but still want to see it was in Kale Salad Meal).
- Two-query shape: one for the Meal list, one selectinload for component hydration. No N+1.
- **100% branch coverage**: happy path, empty, 403, 404, cross-book visibility.

### Story md-3 — Backend: `/v1/meals` filter extensions + `/v1/favorites` meals extension

**Acceptance criteria:**

- `GET /v1/meals` accepts `?archived=true` (returns only archived, sorted by `archived_at DESC`) / `archived=false` or absent (excludes archived). Accepts `?scope=home` (optimized defaults for home grid: exclude archived, sort by `updated_at DESC`, default limit 30).
- `GET /v1/favorites` response gains a `favorited_meals: list[MealSummaryResponse]` key, populated from the `meal_favorites` table. Existing keys unchanged — additive.
- **100% branch coverage**: archived=true/false toggle, scope=home default application, favorites-with-zero-meals returns empty array.

### Story md-4 — Flutter: home grid + favorites carousel render Meals

**Acceptance criteria:**

- `home_screen.dart` fires `getMeals(scope: 'home')` in parallel with recipe fetch inside the existing `Future.wait`.
- Merges recipes + meals into a single `_recipes` list (tagged by `kind='recipe'|'meal'`), sorted by `updated_at DESC`.
- Grid itemBuilder switches on `kind`: `MealTile` for meals, `RecipeCard` for recipes.
- Favorites section iterates both `favorited_recipes` and `favorited_meals` from the extended `/v1/favorites` response; renders both as horizontal cards in the same strip, styled consistently.
- **Zero-Meal regression**: widget test asserts that when `getMeals` returns `[]`, the grid render is bit-identical to pre-epic baseline (no MealTile in tree, no section header, no extra spacing).
- Widget tests: zero-meal, mixed, meals-only fixtures all render correctly. Favorites mixed fixture renders both types in strip.

### Story md-5 — Flutter: search results include Meals with component-match disclosure

**Acceptance criteria:**

- `search_screen.dart` sends `scope=recipes,meals` (default).
- Parses new `my_meals` key; stores in `_myMeals` state.
- Renders new **"My Meals"** section between "My Recipes" and "Public Recipes" — section header uses existing `_buildSectionHeader`.
- Each Meal renders via new `meal_search_tile.dart` (horizontal list row, 100×100 image area showing the foundation collage at small scale, Meal name, book name, decorative "N recipes" badge, and — if `matched_component != null` — a muted third subtitle line **"Matches: <matched_component.name>"**).
- Tap → `context.push('/meals/:id')`.
- Zero-Meal regression: widget test asserts "My Meals" section is NOT rendered when `my_meals` is empty.
- Widget tests: direct-match (no "Matches" line), component-match ("Matches: Lemon Dressing" line visible), mixed results, scope parameter passed as `recipes,meals`, zero-regression.

### Story md-6 — Flutter: "Used in these Meals" on recipe detail

**Acceptance criteria:**

- New widget `meals_using_this_recipe.dart` inserted into `recipe_detail_screen.dart` between the ingredients section and notes section.
- Fires `getMealsUsingRecipe(recipeId)` on mount.
- **Empty response → `SizedBox.shrink()`**. No header, no empty state. Recipe detail layout below the insertion point shifts up by zero pixels when empty.
- Non-empty response → section header "Used in 1 meal" / "Used in N meals" + horizontal `ListView.separated` of 140×120 Meal cards (collage hero, Meal name, decorative "N recipes" badge).
- Loading state: three 140×120 shimmer placeholders while fetching.
- Error state: `SizedBox.shrink()`; error logged to `error_reporter`. Recipe detail never blocks on this fetch.
- Tap card → `context.push('/meals/:id')`.
- **Does NOT mount on `public_recipe_screen.dart`** — explicitly not modified.
- Widget tests: zero meals (bit-identical regression), 1 meal, 5 meals (scroll works), tap-navigation, loading shimmer, error-hides-section.

### Story md-7 — Flutter: archive view includes Meals

**Acceptance criteria:**

- `archived_recipes_screen.dart` calls `getMeals(archived: true)` in parallel with existing archived-recipes call.
- Merges both into one list tagged by `kind`, sorted by `archived_at DESC`.
- Renders mixed items (`MealTile` for meals, existing pattern for archived recipes).
- Restore action on a Meal calls `POST /v1/meals/{id}/restore` (foundation) and removes it from the archive list on success.
- Zero-Meal regression: when `getMeals(archived: true)` returns `[]`, the archive view is bit-identical to pre-epic baseline.
- Widget tests: zero-meal, mixed archive, restore flow.

## Dependencies

- **Blocks**: nothing.
- **Depends on**: `epic-meals-create-and-view` (foundation). Specifically requires: `meals` + `meal_recipes` + `meal_favorites` tables, the `MealSummaryResponse` / component-hydration schemas, `MealTile` widget, `POST/DELETE /v1/meals/{id}/favorite` endpoints, `POST /v1/meals/{id}/restore` endpoint.
- **Parallelizable with**: `epic-meals-calendar`, `epic-meals-sharing-and-ai`. No schema or endpoint conflicts — this epic only reads from foundation's tables and extends search + reverse-lookup.

## Open Questions

**All party-mode open questions are resolved.** Carrying forward to sibling-epic workshops:

- **To `epic-meals-sharing-and-ai`**: the public recipe page (`public_recipe_screen.dart`) intentionally does NOT surface "Used in these Meals" — this was a privacy decision in this epic. When public sharing of Meals lands, the inverse is still correct: a publicly-shared Meal's page may show its component recipes, but a publicly-shared recipe's page must NOT leak which private Meals reference it. If a future product need arises to surface cross-references on public pages, it requires a deliberate opt-in per Meal (not a blanket setting).
- **To `epic-meals-calendar`**: no blocking cross-epic concern from this epic. Calendar adds `meal_events.meal_id` which this epic never reads.
- **To both sibling epics**: the scope-set parsing pattern (`scope=recipes,meals,events`) is now the canonical way to extend `/v1/search`. If calendar wants to add `meal_events` to unified search, use `scope=events` as an additive set member. Do not replace the string-based scope with a different shape.

**Resolved in this refinement** (were open in the draft):

- `UserFavorite` schema — **locked to parallel `meal_favorites` table in foundation**. This epic reads from it; no schema work.
- Search scope parameter shape — **comma-list `scope=recipes,meals`**. Additive, backward-compatible with `scope=recipes` and absent-scope behavior.
- "Used in these Meals" on public recipe pages — **hidden**. Privacy decision.
- Ranking heuristic for Meals vs Recipes — **sectioned, not cross-ranked**. Each tier ranks within itself; the client's section headers make the type explicit.
- Search endpoint shape — **verified as `GET /v1/search`** (router prefix `/search`, handler path `""`). Frontend already hits `/v1/search` via `api_client.search()`. Response gets additive `my_meals` key.

**Nothing to escalate to the user.**
