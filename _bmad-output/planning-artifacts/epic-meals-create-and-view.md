<!-- refined via party-mode 2026-04-18 -->
# Epic: Meals — Create & View (foundation MVP)

## Overview

Today the app is strictly recipe-centric — a meal_event points to a single recipe, and there is no way to group two recipes (Kale Salad + Lemon Dressing) into one named meal. This epic introduces **Meal** as a first-class, reusable entity that bundles 2+ recipes under one name. It ships the end-to-end foundation: backend schema + CRUD API + Flutter Create Meal flow + Meal detail screen + Meal tile in the book grid.

This is the foundational epic for three follow-ons (discoverability, calendar integration, sharing + AI). Those epics are all parallelizable after this one lands.

**Goal (Day-1 user value — before any other epic ships).** On the day this epic lands, Leo can:

1. Long-press "Kale Salad" in his Dinners book, tap "Lemon Dressing" to add it to the selection, hit **Create Meal** in the action bar, name it "Kale Salad Meal," save, and see a new tile in the same grid with a "2 recipes" badge and a 2-up collage of the component thumbnails.
2. Tap the Meal tile, land on a Meal detail screen that shows the collage hero, name, description, and a **component-recipes list** he can tap through to either underlying recipe.
3. Edit the Meal — rename, reorder, add a third component, remove a component (guarded at 2).
4. Archive and restore.

Leo gets value on Day 1 even before the calendar epic ships: the Meal is a **named grouping** he can open and share mentally ("tonight we're having the Kale Salad Meal"). Scheduling, shopping-list expansion, public sharing, and AI pairings are follow-on epics and are explicitly not in scope here.

**Scope boundary — critical.** This epic ONLY creates `meals` + `meal_recipes`. The `meal_events.meal_id` / `meal_recurrence_rules.meal_id` dual-FK columns and their `num_nonnulls(recipe_id, meal_id) <= 1` check constraints land in **epic-meals-calendar**, not here. There is no calendar or shopping-list integration in this epic. There is no public `share_token` endpoint either — the column exists on `meals` (to avoid a second migration later) but no write or read path touches it in this epic; that ships in **epic-meals-sharing-and-ai**.

## End-User Flow

### Primary path — multi-select from book detail

1. Leo opens "Dinners" (existing `recipe_book_detail_screen.dart`).
2. He long-presses "Kale Salad" — the existing multi-select mode activates; the AppBar switches to "1 selected" with the existing select-all / close affordances.
3. He taps "Lemon Dressing." AppBar: "2 selected."
4. The existing bottom action bar (`_BulkActionButton` row: Move, Tags, Archive) **gains a new leading action: Create Meal**. It is disabled at 1 selection and enabled at ≥2.
5. Tapping Create Meal opens `create_meal_sheet.dart` as a modal bottom sheet:
   - **Name** field (autofocus), pre-filled with the first two selected recipe names joined by `" + "` (truncated to 60 chars with ellipsis).
   - **Description** (optional, single-line).
   - **Components preview**: a horizontal scroll strip of the selected recipe thumbnails with names underneath. Tap-and-hold on a thumbnail to remove from the draft (with an undo snackbar). The draft must retain ≥2; the Create button disables if it drops below.
   - Primary button: **Create**. Secondary: Cancel.
6. Creating dispatches `POST /v1/recipe-books/{book_id}/meals`, dismisses the sheet on success, invalidates both the book's recipe list and Meals list, and the grid reloads.
7. The book grid now contains a new tile styled like a recipe tile but with a **"2 recipes" badge** (non-tappable — decorative only; tapping anywhere on the tile opens the Meal), a 2-up collage hero, and the Meal name. Existing recipe tiles are unchanged.

### Secondary path — "+ New Meal" from the book header

8. From the book detail overflow menu (`PopupMenuButton`), Leo picks **New Meal**. This opens `create_meal_sheet.dart` in its second mode: Name + embedded `recipe_multiselect_picker.dart` (defaults to the current book's recipes, searchable across any book the user can read). Save disabled until `name.trim().isNotEmpty && components.length >= 2`.

### Meal detail

9. Tapping a Meal tile routes to `/meals/:mealId` (`meal_detail_screen.dart`):
   - Sliver app bar with **ComponentCollageHero** (collage of up to 4 component thumbnails — see Frontend Changes § Collage Layout for exact layouts).
   - Title row: Meal name + description.
   - Action bar (6 actions in a horizontal row): **Favorite** (writes to `meal_favorites` — wired live v1), **Plan for Date** (disabled placeholder v1, tooltip "Available when calendars ship"), **Add to Shopping List** (disabled placeholder v1, tooltip "Schedule first"), **Share** (disabled placeholder v1, tooltip "Available when sharing ships"), **Archive**, **Edit**.
   - **Component-recipes list**: one `ComponentRow` per component — thumbnail + name + book-of-origin label + prep/cook time chips + trailing right-chevron. Tap opens the underlying recipe detail via `context.push('/recipes/$id')`.
10. From Meal detail, **Edit** pushes `/meals/:mealId/edit` (`meal_edit_screen.dart`):
    - Inline-editable name + description.
    - Drag-to-reorder list (calls `POST /v1/meals/{id}/reorder` on drop; optimistic reorder with rollback on failure).
    - **Add Recipe** FAB → `recipe_multiselect_picker.dart` (current book default, searchable). Duplicate components are visually disabled with an "Already added" label.
    - Swipe-to-delete per component; confirmation snackbar with Undo. If removal would drop below 2, the swipe is rejected with a snackbar "A meal needs at least 2 recipes. Remove this one only after adding a replacement."
    - App bar: **Cancel** / **Save**. (Name/description save on Save; reorder and component add/remove commit immediately — they are their own endpoints. This matches existing recipe-edit ergonomics.)

### What does not change

Single-recipe creation is untouched. Recipe detail is untouched. The book grid layout is the same two-column (or responsive) grid with the same spacing. Existing multi-select actions (Move, Tags, Archive) are preserved; Create Meal is an **additional** leading action, never replacing an existing one.

## Frontend Changes

Touches `app/lib/features/recipes/` and `app/lib/features/recipe_books/`; adds a new `app/lib/features/meals/` directory.

### New files

- **`app/lib/features/meals/models/meal.dart`** — `Meal` + `MealComponentSummary` data classes with JSON serializers. `Meal`: id, name, description, recipeBookId, shareToken (nullable, not read in v1 but present on the wire so the model stays stable), archivedAt, createdAt, updatedAt, components. `MealComponentSummary`: recipeId, name, imageUrl, prepTime, cookTime, bookName, orderIndex, available (bool).
- **`app/lib/features/meals/services/meal_service.dart`** — typed API client: `listMealsInBook`, `listMeals`, `getMeal`, `createMeal`, `updateMeal` (name/description only), `addRecipeToMeal`, `removeRecipeFromMeal`, `reorderMealComponents`, `archiveMeal`, `restoreMeal`, `favoriteMeal`, `unfavoriteMeal`.
- **`app/lib/features/meals/providers/meals_provider.dart`** — Riverpod providers: `mealsByBookProvider(bookId)` (FutureProvider.family), `mealByIdProvider(id)`, and an `invalidateMeal(ref, id)` helper for post-write cache busting.
- **`app/lib/features/meals/meal_detail_screen.dart`** — `CustomScrollView` + sliver app bar (mirrors the recipe-detail shell). Renders `ComponentCollageHero`, title/description, action bar, component list.
- **`app/lib/features/meals/meal_edit_screen.dart`** — inline-edit UX with drag-to-reorder + Add Recipe FAB.
- **`app/lib/features/meals/widgets/create_meal_sheet.dart`** — modal sheet with two entry modes (pre-supplied components from multi-select, or embedded picker from "+ New Meal").
- **`app/lib/features/meals/widgets/recipe_multiselect_picker.dart`** — searchable multi-select list; defaults to the Meal's book, can search across all accessible books. Visually disables already-attached components in edit mode ("Added" badge).
- **`app/lib/features/meals/widgets/component_collage_hero.dart`** — the collage (layouts spec below).
- **`app/lib/features/meals/widgets/component_row.dart`** — one row of the component list.
- **`app/lib/features/meals/widgets/meal_tile.dart`** — Meal-grid tile (decision below).

### Modified files

- **`app/lib/features/recipe_books/recipe_book_detail_screen.dart`** — adds "Create Meal" as the leading action in the existing multi-select action bar (enabled at ≥2); adds "New Meal" to the header overflow `PopupMenuButton`; fetches both recipes AND Meals for the book and merges them into a single grid stream (Meals interleaved by `updated_at`).
- **`app/lib/core/router/app_router.dart`** — adds `/meals/:mealId` → `MealDetailScreen` and `/meals/:mealId/edit` → `MealEditScreen`. **Both are full screens**, not modals — this matches the existing recipe-detail pattern and avoids an awkward nested-sheet when the edit screen itself launches a picker sheet.

### Decision: RecipeCard — **fork, not extend** (was the open question)

We chose **fork**: introduce a standalone `meal_tile.dart` widget alongside the existing `_RecipeCard` (which stays in `recipe_book_detail_screen.dart` untouched). The book grid decides which widget to instantiate based on item type.

**Why fork:**
- The card's visual differences go beyond a badge: the hero area switches from a single image to a 1/2/3/4-up collage with different padding math. Extending means the card has two render paths inside it, and every future card tweak has to reason about both. Forking keeps each tile as simple as what it renders.
- `_RecipeCard` today is already a private nested widget inside `recipe_book_detail_screen.dart` (see lines 971–1136). It is not reused anywhere. Forking to a new `meal_tile.dart` as a sibling is a one-file diff with zero risk to the recipe path.
- "Two widgets to keep in sync" is a weak objection when neither widget has non-trivial logic — the shared vocabulary is tokens (spacing, radius, badge style) which live in `theme.dart` and are referenced from both widgets.
- Extending creates a prop-shape that leaks a future "Meal with hero image" column through the RecipeCard API (if we ever add one). Separation now keeps that future cheap.

**Card badge.** The "N recipes" badge is **decorative only** (non-tappable). Tapping anywhere on the tile opens the Meal detail. Rationale: tappable sub-affordances on a grid tile fight with tap-to-open and with long-press-to-select. Keep the tile monolithic.

### Collage hero layouts (`component_collage_hero.dart`)

Fixed aspect ratio matching the existing recipe hero (~16:9 at the card scale, full-bleed on detail screen). All layouts use `fit: BoxFit.cover`. Gap between cells: 2 logical pixels. Placeholder for missing images: the same `Icons.restaurant` outlined placeholder pattern used by `_RecipeCard` today.

- **1 component** (legal only if a component was unavailable after save — not a creation state): single image full-bleed. Matches the single-recipe hero visually. Adds a subtle top-right "1 of N" chip when one or more components are unavailable.
- **2 components**: split vertically, each component takes 50% width, full height.
- **3 components**: first component left 50% full height; right column split horizontally into the 2nd and 3rd, each 50% height.
- **4+ components**: 2×2 grid. The 4th cell shows the 4th thumbnail with a `+N` overlay chip in the bottom-right when component count > 4 (e.g. "+2" for a 6-component meal).

### Empty / loading / error states (spec per surface)

- **Book grid — loading**: existing `CircularProgressIndicator` (unchanged). Meals + recipes loaded in parallel; grid renders when both complete. If one of the two fails, render the successful list + an `ErrorBanner` above the grid reading "Some content didn't load" with a Retry button.
- **Book grid — empty with neither recipes nor Meals**: existing `_buildBookEmptyState` (unchanged — the CTAs are still recipe-centric; "Create a Meal" is not a valid cold-start since there are no recipes to combine).
- **Create Meal sheet — component archived before Save**: if any of the selected `component_recipe_ids` is archived between selection and Create, the POST returns a 422 with `{code: "COMPONENT_UNAVAILABLE", recipe_ids: [...]}`. The sheet catches this, shows an inline error banner "Kale Salad was archived. Remove it to continue.", disables Create, and surfaces a Remove button per offending row. Regaining ≥2 re-enables Create.
- **Create Meal sheet — <2 components**: Create button disabled with a helper subtitle "A meal needs at least 2 recipes."
- **Meal detail — loading**: sliver app bar with shimmer placeholder for the collage; skeleton rows for the component list (match the existing recipe-detail shimmer treatment).
- **Meal detail — all components unavailable**: the collage renders 4 placeholder cells; the hero chip reads "All components unavailable." The component list renders muted rows with "Unavailable" labels and a subdued description: "Components may have been archived or their books unshared." Action bar: Favorite, Archive, Edit remain enabled. Plan/Shopping/Share stay in their disabled-placeholder state.
- **Meal detail — partial unavailability**: unavailable rows render muted with "Unavailable"; a banner above the list reads "Some components are unavailable." In edit mode, the banner reads "Remove unavailable components or wait until their books are re-shared" and unavailable rows gain a Remove action.
- **Meal edit — 5th component added to already-saved Meal**: no special case. Add Recipe picker adds normally; the collage just switches to the `+N` overlay layout on the next render.
- **Meal edit — save conflict (meal updated by another device)**: current writes are endpoint-per-field so there is no coarse optimistic-lock story in v1. If a name/description PATCH 409s, show a snackbar "Meal was updated elsewhere — reloading" and re-fetch.

### Widget tests (must exist, non-negotiable)

- `create_meal_sheet_test.dart`: sheet enables Create at ≥2, disables at <2; happy path submits correct payload; cancel discards; 422 COMPONENT_UNAVAILABLE response renders the inline error + Remove affordance.
- `meal_detail_screen_test.dart`: renders collage + name + components; tap-through to recipe detail; partial-unavailability banner; all-unavailable empty-hero chip.
- `meal_edit_screen_test.dart`: reorder persists via endpoint call; swipe-remove at 3 components succeeds, at 2 rejects; add-recipe flow.
- `meal_tile_test.dart`: renders with 1/2/3/4 components and the `+N` overlay at 5+; tap opens `/meals/:id`.
- `recipe_multiselect_picker_test.dart`: search across books; "Added" badge on already-attached components.
- `meals_provider_test.dart`: invalidation helper busts both `mealByIdProvider(id)` and `mealsByBookProvider(bookId)`.

## Backend Changes

### Models

- **`libraries/utils/utils/models/meal.py`** (new). `Meal` SQLAlchemy model. Columns (matching architecture.md § Addendum 2026-04-18):
  - `id` UUID PK, `name` str not null, `description` text nullable.
  - `recipe_book_id` UUID FK `recipe_books.id` ondelete CASCADE, not null, indexed.
  - `share_token` str nullable — column exists but no endpoint in this epic touches it; partial unique index `WHERE share_token IS NOT NULL`.
  - `archived_at`, `created_at`, `updated_at` inherited from `Base`.
  - Relationship: `components: Mapped[list[MealRecipe]]`, cascade="all, delete-orphan", ordered by `order_index`.
- **`libraries/utils/utils/models/meal_recipe.py`** (new). `MealRecipe` join. Columns:
  - `meal_id` UUID FK `meals.id` ondelete CASCADE, PK.
  - `recipe_id` UUID FK `recipes.id` **ondelete RESTRICT** (enforce in-use check at recipe delete; recipe archive is soft-delete and does NOT cascade).
  - `order_index` int not null default 0.
  - `created_at` from `JoinsBase`.
  - Composite PK `(meal_id, recipe_id)`. Secondary index on `recipe_id`.
- **`libraries/utils/utils/models/meal_favorite.py`** (new). Parallels `user_favorites`. Columns: `user_id` PK (FK users cascade), `meal_id` PK (FK meals cascade), inherits `JoinsBase`. This is a **parallel favorites table** — polymorphic unification with `user_favorites` is explicitly deferred.
- **`libraries/utils/utils/models/__init__.py`** (modify) — register the three new models.

### Schemas

- **`services/api/src/schemas/meal.py`** (new):
  - `MealCreateRequest`: `name` (str, 1–200 chars), `description` (optional str ≤ 2000), `component_recipe_ids` (`list[UUID]`, `min_length=2`, unique). Validator: reject duplicates at the schema layer so the handler never has to.
  - `MealUpdateRequest`: `name`, `description` both optional. (Component changes go through the dedicated add/remove/reorder endpoints — this simplifies transaction shape and matches how the frontend actually writes.)
  - `MealComponentAddRequest`: `recipe_id`, `order_index` optional.
  - `MealReorderRequest`: `recipe_ids` (`list[UUID]`, min_length=2, unique).
  - `MealComponentResponse`: `recipe_id`, `name`, `image_url`, `prep_time`, `cook_time`, `book_name`, `order_index`, `available` (bool), `last_known_name` (optional, set when `available=false`).
  - `MealResponse`: id, name, description, recipe_book_id, archived_at, created_at, updated_at, components (list).
  - `MealSummaryResponse`: id, name, component_count, top 4 component image_urls, updated_at — for grid lists.

### Handlers (`services/api/src/api/v1/meals/`, one per verb)

- `create_meal.py` — `POST /v1/recipe-books/{book_id}/meals`. Enforces book write membership; validates every component is readable by the user (404 if not); rejects <2 with 422; rejects duplicate component_ids at schema layer; creates `meals` + `meal_recipes` rows in a **single SQLAlchemy session transaction**; returns `MealResponse`.
- `get_meal.py` — `GET /v1/meals/{meal_id}`. Auth: **book read membership** on the Meal's `recipe_book_id` via existing `recipe_book_user` check. **No share_token bypass in this epic** — public endpoint ships with sharing epic. Eager-loads components with `selectinload(Meal.components).selectinload(MealRecipe.recipe).selectinload(Recipe.recipe_book)` (decision below). Marks unavailable components in the response.
- `list_meals_in_book.py` — `GET /v1/recipe-books/{book_id}/meals`. Paginated, returns `MealSummaryResponse[]`.
- `list_meals.py` — `GET /v1/meals`. Paginated across all books the user can read.
- `update_meal.py` — `PATCH /v1/meals/{meal_id}`. Name/description only. Write-membership check.
- `archive_meal.py` — `POST /v1/meals/{meal_id}/archive`. Soft-archive (sets `archived_at`). Writes an audit row to `error_logs` (service="audit").
- `restore_meal.py` — `POST /v1/meals/{meal_id}/restore`.
- `add_recipe_to_meal.py` — `POST /v1/meals/{meal_id}/recipes`. Rejects duplicate (409). Rejects recipe the user can't read (404). Default `order_index = max(existing) + 1`.
- `remove_recipe_from_meal.py` — `DELETE /v1/meals/{meal_id}/recipes/{recipe_id}`. Rejects if it would leave <2 (422, code `MIN_COMPONENTS`).
- `reorder_meal_components.py` — `POST /v1/meals/{meal_id}/reorder`. Accepts an ordered list of `recipe_id`s that must exactly equal the current component set (same length, same members — reject with 422 `REORDER_MISMATCH` otherwise). Updates all `order_index` values in one transaction.
- `favorite_meal.py` / `unfavorite_meal.py` — `POST/DELETE /v1/meals/{meal_id}/favorite`. Writes to `meal_favorites`.

### Router

- **`services/api/src/routers/v1/meal_router.py`** (new). Registers handlers under `/api/v1/meals` and `/api/v1/recipe-books/{book_id}/meals`. Include in `services/api/src/main.py`.

### Authorization

- New dependency `services/api/src/dependencies/meal_access.py`:
  - `require_meal_read_access(meal_id, user) -> Meal` — loads Meal, 404 if not found, checks `recipe_book_user` for any role including `viewer`; 403 if not a member.
  - `require_meal_write_access(meal_id, user) -> Meal` — same but requires `owner` or `editor`.
  - `require_book_write_access(book_id, user) -> RecipeBook` — reused by `create_meal` and `list_meals_in_book`.
- **No XOR logic in this epic**. The XOR story (meal_id XOR recipe_id on meal_events) lives in epic-meals-calendar and does not appear in any handler, schema, or test here. Do not add `num_nonnulls` check constraints in this migration.

### Service layer

- **`libraries/utils/utils/services/meal_service.py`** (new):
  - `create_with_components(book_id, name, description, recipe_ids, *, user_id) -> Meal` — atomic.
  - `add_component`, `remove_component`, `reorder_components`, `archive`, `restore`.
  - `hydrate_components(meal, *, user_id) -> list[MealComponentResponse]` — joins to recipes + recipe_books, marks `available=False` for components the user can no longer read (archived recipe OR book no longer shared). This is **eager-loaded via `selectinload`, not `joinedload`** — decision below.

### Decision: selectinload vs. joinedload

We chose **`selectinload`** for component hydration.

- Component count per Meal is typically 2–6, realistic cap ~20. `joinedload` would emit one wide row per component (a cartesian-style expansion of Meal × components × recipe × recipe_book fields) — each Meal's row repeats its base columns N times over the wire.
- `selectinload` issues a second IN-batched query for components, which PostgreSQL indexes efficiently on `meal_recipes.meal_id` and makes the list-of-meals endpoint's N-query shape collapse to 2 queries regardless of component count.
- The `list_meals` endpoint in particular — which can return 50+ Meals per page — would see quadratic row duplication with `joinedload` and no deduplication benefit.
- `selectinload` also plays cleanly with async SQLAlchemy 2.0, our default.

### Rate limiting, duplicate-name policy, transaction-rollback

- **Rate limiting**: no bespoke rate limit on `create_meal`. It is a small transactional insert (one Meal row + N join rows where N ≤ ~20 realistically). The existing API Gateway per-user throttles are sufficient.
- **Duplicate Meal name in the same book**: **allow, don't warn**. Recipe names are not unique within a book today ("Pasta" can appear twice) and adding a divergent rule for Meals would be inconsistent and user-hostile (Leo can legitimately have "Taco Tuesday" week after week). If the user duplicates intentionally the UI is responsible for disambiguation, not the DB.
- **Transaction rollback on partial failure**: every multi-row write (create, reorder, bulk add/remove in update) uses a single `async with session.begin()` block. A failure anywhere in the block rolls back both the Meal and its join rows. Tests must assert that a failed join insert leaves no orphan Meal row.

### Component-availability handling on reads

On `get_meal` and `list_meals*`, the service eager-loads components with a LEFT JOIN-style selectinload chain to `recipes` and `recipe_books`, then filters in Python: a component is `available=True` iff the recipe is not archived AND the current user has read membership on that recipe's book. Unavailable components are returned with `available=false` + `recipe_id` + `last_known_name` (pulled from the join's stale `recipes.name`). Read surfaces hide; edit surfaces expose a Remove action.

### Tests (`services/api/tests/`)

- `test_meal_router.py`:
  - **Per handler, minimum matrix**: happy path, validation reject, auth-fail (non-book-member), 404 (not found), transaction-rollback on partial failure.
  - `create_meal`: happy; reject <2; reject duplicate component_id; reject unreadable component; reject non-book-member; rollback when a join insert fails (simulated via SQL error injection).
  - `get_meal`: happy hydration; read-member of book but not editor can still get; non-member 403; not-found 404; component-unavailability (archived recipe); component-unavailability (book no longer shared).
  - `list_meals_in_book`, `list_meals`: happy; pagination; excludes archived; excludes Meals from books the user can't read.
  - `update_meal`: happy name/description; 403 for non-writer; 404.
  - `add_recipe_to_meal`: happy; 409 duplicate; 404 unreadable recipe; 403 non-writer.
  - `remove_recipe_from_meal`: happy at 3 → 2; reject at 2 → 1 (422 MIN_COMPONENTS); 403; 404.
  - `reorder_meal_components`: happy; reject set mismatch; 403.
  - `archive_meal` / `restore_meal`: happy; audit row written; 403.
  - `favorite_meal` / `unfavorite_meal`: happy; idempotent (double favorite is a no-op); 403 for non-reader.
- `test_meal_service.py`: `hydrate_components` availability logic (archived-recipe, unshared-book, happy); reorder atomicity; archive idempotency.
- `test_meal_model.py`: cascade on book delete; `meal_recipes` RESTRICT on recipe hard-delete (verified by expected IntegrityError — this protects against accidental ORM hard-deletes even though user-facing deletes are archives).
- **Coverage**: 100% branch on every new handler. `coverage.xml` from the api test CI job is the source of truth; any uncovered branch fails the build.

## Infrastructure Changes

None.

- **Migration**: one alembic revision, `<yyyymmddhhmm>_add_meals_and_meal_recipes_and_meal_favorites.py`. Creates three tables (`meals`, `meal_recipes`, `meal_favorites`) and their indexes. No backfill required. No changes to `meal_events` or `meal_recurrence_rules` in this migration — those land in epic-meals-calendar.
- **Migration ordering / independence**: this migration is safe to run independently of any calendar epic migration. Both target disjoint tables. The calendar epic's migration adds `meal_events.meal_id` (+ constraint) and `meal_recurrence_rules.meal_id` (+ constraint), both of which FK into `meals` — so the calendar migration must depend on this one, but this one has no dependency on the calendar migration.
- **Reversibility**: `downgrade()` drops the three tables. Idempotent.
- **No new AWS resources, no new IAM, no new secrets, no new env vars** — confirmed in PRD addendum and architecture addendum. `docker-compose` dev loop: unchanged. No changes to `migrator`, `worker`, or `api` Dockerfiles.
- **CI**: covered by `npx nx run api:test`. 100% API coverage is pinned by CLAUDE.md; breakage here breaks every downstream push.
- **Deploy path**: standard `npx nx run api:docker-build` + `npx nx run migrator:docker-build`. Docker-compose `migrate` profile runs the new revision in dev. Prod deploy is a normal ECS task roll with the migrator task run once before API task swap (existing pattern).

## Design Principles (refined)

1. **Meal is a Recipe's sibling, not its subclass.** Meal lives in a recipe_book (FK + inherits sharing), has its own detail screen, has its own tile. Meal is NOT a Recipe — it carries no ingredients, steps, or hero image directly. Component recipes provide all of those.
2. **Component recipes can come from ANY book the user can read.** A Meal in a personal book can include a component from a shared book. If that book is later unshared, the component is hidden on read surfaces and flagged on edit surfaces as "Unavailable — remove or wait until re-shared." The Meal is never deleted as a side effect.
3. **2+ is the floor, enforced at three layers.** DB: implicit via service-layer transaction (no explicit CHECK on the count in this epic — we pay the round-trip). API: `MealCreateRequest` has `min_length=2` on `component_recipe_ids`; `remove_recipe_from_meal` rejects at 2. UI: the Create button disables at <2; swipe-remove at 2 rejects.
4. **Fork RecipeCard into a dedicated MealTile.** (Was an open question; now decided — see Frontend Changes § Decision: RecipeCard.)
5. **Create Meal is NOT a wizard.** One modal sheet with name + (optionally) a picker.
6. **Multi-select action bar is the primary fast-path.** Standalone "+ New Meal" is the secondary path.
7. **Archive cascades from the book, not from the component recipe.** Archiving a book archives its Meals via standard cascade. Archiving a component recipe does NOT archive Meals that reference it — the component is hidden on reads instead.
8. **No Meal hero image in v1.** Collage of up to 4 component thumbnails is the hero. `meal.image_url` is explicitly not added; if the collage is insufficient the follow-up lands in sharing-and-ai (polish).
9. **MCP tools + AI pairings ship in `epic-meals-sharing-and-ai`.** Not here.
10. **Meal endpoints live at both `/meals` (flat) and `/recipe-books/{book_id}/meals` (nested)**, mirroring recipes.
11. **Disabled-with-tooltip > half-wired cross-epic coupling.** Plan for Date, Add to Shopping List, and Share on the Meal detail action bar are disabled placeholders in v1 (was an open question; decided — see Stories mcv-6 and Open Questions).
12. **Favorite is wired in v1.** It's the only action that has no cross-epic dependency, and it provides an immediate low-risk "pinning" surface for the user.

## File Structure

```
app/lib/features/meals/              [NEW]
  models/meal.dart
  services/meal_service.dart
  providers/meals_provider.dart
  meal_detail_screen.dart
  meal_edit_screen.dart
  widgets/
    create_meal_sheet.dart
    recipe_multiselect_picker.dart
    component_collage_hero.dart
    component_row.dart
    meal_tile.dart

app/lib/features/recipe_books/       [MODIFY]
  recipe_book_detail_screen.dart     +Create Meal action in bulk bar,
                                     +New Meal overflow item, meals in grid

app/lib/core/router/app_router.dart  [MODIFY]  +/meals/:id, +/meals/:id/edit

libraries/utils/utils/models/        [NEW]
  meal.py
  meal_recipe.py
  meal_favorite.py
libraries/utils/utils/models/__init__.py  [MODIFY]

services/api/src/schemas/            [NEW]
  meal.py

services/api/src/api/v1/meals/       [NEW dir, 11 handlers]
  create_meal.py
  get_meal.py
  list_meals.py
  list_meals_in_book.py
  update_meal.py
  archive_meal.py
  restore_meal.py
  add_recipe_to_meal.py
  remove_recipe_from_meal.py
  reorder_meal_components.py
  favorite_meal.py                   (includes unfavorite as DELETE)

services/api/src/routers/v1/         [NEW]
  meal_router.py

services/api/src/main.py             [MODIFY]  include meal_router

services/api/src/dependencies/       [NEW]
  meal_access.py

services/migrator/migrations/versions/ [NEW]
  <yyyymmddhhmm>_add_meals_and_meal_recipes_and_meal_favorites.py

libraries/utils/utils/services/      [NEW]
  meal_service.py

services/api/tests/                  [NEW]
  test_meal_router.py
  test_meal_service.py
  test_meal_model.py
```

## Stories

### Story mcv-1 — Backend: meals + meal_recipes + meal_favorites migration and models

**Acceptance criteria:**

- New alembic revision `<yyyymmddhhmm>_add_meals_and_meal_recipes_and_meal_favorites.py` creates:
  - `meals` table with columns from architecture.md (id, name, description, recipe_book_id FK ondelete CASCADE, share_token nullable, archived_at, created_at, updated_at); partial unique index on `share_token WHERE share_token IS NOT NULL`; index on `(recipe_book_id)`.
  - `meal_recipes` join with composite PK `(meal_id, recipe_id)`, FKs (meal_id CASCADE, recipe_id RESTRICT), `order_index int not null default 0`, `created_at`. Secondary index on `recipe_id`.
  - `meal_favorites` join paralleling `user_favorites` — composite PK `(user_id, meal_id)`, both FKs CASCADE.
- `libraries/utils/utils/models/meal.py`, `meal_recipe.py`, `meal_favorite.py` added; `__init__.py` registers all three.
- Migration `upgrade()` and `downgrade()` are both reversible; `downgrade()` drops all three tables.
- `npx nx run migrator:migrate` runs clean against a fresh DB; existing data untouched.
- **Test**: migration round-trip (up + down + up) leaves no artifacts; `test_meal_model.py` verifies cascade on book delete and RESTRICT on recipe hard-delete.
- **No changes** to `meal_events` or `meal_recurrence_rules` in this migration.

### Story mcv-2 — Backend: Meal CRUD endpoints (create, get, list, update, archive/restore) + service

**Acceptance criteria:**

- Handlers under `services/api/src/api/v1/meals/`: `create_meal`, `get_meal`, `list_meals`, `list_meals_in_book`, `update_meal`, `archive_meal`, `restore_meal`. All follow the `Endpoint`-subclass pattern.
- `POST /v1/recipe-books/{book_id}/meals` accepts `{name, description?, component_recipe_ids: [UUID]}` (≥2 required, unique); validates each component is readable by the user (404 `COMPONENT_UNREADABLE` on failure); creates Meal + join rows in a single transaction.
- `GET /v1/meals/{id}` returns `MealResponse` with hydrated components (via `selectinload`); marks `available=false` + `last_known_name` for archived-recipe or unshared-book components.
- `GET /v1/meals` and `GET /v1/recipe-books/{book_id}/meals` paginate; exclude archived by default (query param `include_archived=true` to include).
- `PATCH /v1/meals/{meal_id}` updates name/description only; 403 non-writer.
- `archive_meal` / `restore_meal` toggle `archived_at` and write an audit row to `error_logs` (`service="audit"`, `error_type="MealArchive"` / `"MealRestore"`).
- Auth: every mutation requires `require_meal_write_access` (owner or editor on book); every read requires `require_meal_read_access`.
- **100% branch coverage**: happy, validation reject (<2, duplicate, unreadable component), auth-fail, 404, transaction-rollback-on-partial-failure.

### Story mcv-3 — Backend: component add/remove/reorder endpoints + favorite

**Acceptance criteria:**

- `POST /v1/meals/{id}/recipes` adds a component `{recipe_id, order_index?}`; rejects duplicate (409 `COMPONENT_DUPLICATE`); rejects unreadable recipe (404); 403 non-writer.
- `DELETE /v1/meals/{id}/recipes/{recipe_id}` removes a component; rejects if it would leave <2 (422 `MIN_COMPONENTS`).
- `POST /v1/meals/{id}/reorder` accepts an ordered `recipe_ids` list; rejects set-mismatch (422 `REORDER_MISMATCH`); updates all `order_index` values in one transaction.
- `POST /v1/meals/{id}/favorite` / `DELETE /v1/meals/{id}/favorite` toggle `meal_favorites`; idempotent; requires read membership.
- Auth helper reuse: `require_meal_write_access` on add/remove/reorder; `require_meal_read_access` on favorite.
- **100% branch coverage** on all branches (happy, duplicate-reject, last-two-reject, reorder mismatch, auth-fail, 404, transaction-rollback).

### Story mcv-4 — Flutter: Meal model, service, provider, router

**Acceptance criteria:**

- `lib/features/meals/models/meal.dart` — `Meal`, `MealComponentSummary` data classes with JSON serializers (round-trip unit-tested).
- `lib/features/meals/services/meal_service.dart` — typed API client hitting all mcv-2 + mcv-3 endpoints. Parses `COMPONENT_UNAVAILABLE`, `COMPONENT_DUPLICATE`, `MIN_COMPONENTS`, `REORDER_MISMATCH` into typed exceptions.
- `lib/features/meals/providers/meals_provider.dart` — `mealsByBookProvider(bookId)` + `mealByIdProvider(id)` + `invalidateMeal(ref, id)` helper.
- `app/lib/core/router/app_router.dart` — new `/meals/:mealId` and `/meals/:mealId/edit` routes wired to the new screens (stubs in this story are acceptable if the screens haven't landed yet; the router wiring must compile and route).
- **Tests**: service serialization round-trip; provider invalidation behavior.

### Story mcv-5 — Flutter: Create Meal (multi-select entry + standalone)

**Acceptance criteria:**

- `recipe_book_detail_screen.dart` multi-select action bar gains a **Create Meal** button as the leading action, enabled at ≥2 selected recipes, disabled below.
- Tapping opens `create_meal_sheet.dart` in multi-select mode: Name (autofocus, pre-filled with first two component names joined by `" + "`, truncated 60 chars) + Description + horizontal component preview strip (tap-hold to remove, must retain ≥2) + Create.
- On success: the sheet dismisses, `invalidateMeal(ref, id)` + `mealsByBookProvider(bookId).invalidate()` fire, and the book grid reloads.
- Header overflow gains a **New Meal** item. Tapping opens `create_meal_sheet.dart` in standalone mode: Name + embedded `recipe_multiselect_picker.dart` (defaults to current book; searchable across any book the user can read). Save disabled until `name.trim().isNotEmpty && components.length >= 2`.
- `422 COMPONENT_UNAVAILABLE` response renders the inline error banner + Remove affordance per offending row (spec: Frontend Changes § Empty/loading/error).
- **Widget tests**: Create Meal enables at 2; Create disables at <2 during edit; happy path submits and invalidates; cancel discards; COMPONENT_UNAVAILABLE banner + Remove flow.

### Story mcv-6 — Flutter: Meal detail + edit screen

**Acceptance criteria:**

- `meal_detail_screen.dart` loads a Meal by id via `mealByIdProvider`, renders `ComponentCollageHero` (1/2/3/4-up + `+N` overlay per spec), name, description, action bar (Favorite — **live in v1**; Plan for Date / Add to Shopping List / Share — **disabled-with-tooltip placeholders per Principle 11**; Archive; Edit), and a `ComponentRow` list.
- Favorite toggle uses `favorite_meal.py` / `unfavorite_meal.py` endpoints; optimistic UI with rollback on error.
- Tapping a component row opens that recipe's detail screen via `context.push('/recipes/$recipeId')`.
- Partial-unavailability banner + muted rows; all-unavailable chip on hero; edit-mode Remove action on unavailable rows.
- `meal_edit_screen.dart`: inline name + description edit (Save commits via `update_meal`), drag-to-reorder (commits per drop via `reorder`), Add Recipe FAB → `recipe_multiselect_picker.dart`, swipe-to-delete with ≥2 guard.
- **Widget tests**: render with 2/3/4/5 components; reorder persists; remove at 3→2 succeeds, at 2→1 rejects with snackbar; unavailable-component rendering; favorite toggle round-trip.

### Story mcv-7 — Flutter: Meal tile in book grid (fork path)

**Acceptance criteria:**

- New `meal_tile.dart` as a sibling of `_RecipeCard` in the book grid. `_RecipeCard` is **not modified**.
- Book detail grid fetches recipes AND Meals in parallel (`Future.wait`), merges into a single ordered stream sorted by `updated_at DESC`, renders mixed tiles in the same `GridView.count`.
- Meal tiles show the 1/2/3/4-up collage hero, the Meal name (single line, ellipsis), an optional first-line description chip when present, and a **decorative "N recipes" badge** in the bottom-right (non-tappable; whole-tile tap opens `/meals/:id`).
- Archived-Meal view: the existing archived-recipes surface is extended to include archived Meals (same list, same sort; Meal tiles rendered identically).
- **Widget tests**: mixed grid renders both tile types; badge shows correct count; tap navigates to `/meals/:id`; archived view includes archived Meals.

## Dependencies

- **Blocks**: `epic-meals-discoverability`, `epic-meals-calendar`, `epic-meals-sharing-and-ai` all depend on this foundation.
- **Depends on**: nothing. `meals` + `meal_recipes` + `meal_favorites` tables are greenfield; `recipe_book_detail_screen.dart` and `_RecipeCard` already exist. No migration ordering against in-flight epics is required.

## Open Questions

All party-mode open questions are **resolved**. Carrying forward to sibling-epic workshops:

- **To epic-meals-calendar**: this epic does NOT add `meal_events.meal_id` / `meal_recurrence_rules.meal_id` or any `num_nonnulls` check constraint. That migration is owned entirely by calendar. Calendar's migration must depend on this one (the meals table must exist before an FK can reference it).
- **To epic-meals-discoverability**: the reverse-lookup endpoint (`GET /v1/recipes/{recipe_id}/meals`) is NOT shipped here — it lands with discoverability. Recipe detail screens stay untouched.
- **To epic-meals-sharing-and-ai**: `share_token` column exists on `meals` but no endpoint reads or writes it. Public `GET /v1/public/meals/{share_token}` ships with sharing. MCP tools ship with sharing.
- **To all sibling epics**: the Meal detail action bar in v1 has three **disabled-with-tooltip** slots for Plan-for-Date, Add-to-Shopping-List, and Share. When sibling epics land they should wire these in place, not re-introduce them as new actions — the icon + position + tooltip copy are contracts already seen by the user.

**Nothing to escalate to the user.** The two questions in the draft (RecipeCard fork-vs-extend; Add-to-Shopping-List wiring before calendar) are resolved in the body (fork; disabled placeholder).
