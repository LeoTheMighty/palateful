# Story 2.5: Archive & Restore Recipes

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to archive recipes I no longer actively use and restore them anytime,
so that my active collection stays clean without ever losing a recipe.

## Acceptance Criteria

1. Given I own a recipe, when I swipe to archive (or use the long-press menu), then the recipe is removed from active views (home, books, search)
2. Given a recipe has been archived, then the recipe is soft-deleted via `archived_at` — no data is physically removed
3. Given I have archived recipes, when I access the archive view, then I can see all archived recipes
4. Given I am viewing an archived recipe, when I tap restore, then the recipe is restored to active status with one tap
5. Given an archived recipe, then all version history and fork lineage references are preserved

## Tasks / Subtasks

- [ ] Task 1: Convert DeleteRecipe from hard delete to soft delete (archive) (AC: #1, #2)
  - [ ] Modify `services/api/src/api/v1/recipe/delete_recipe.py`: change `self.database.delete(recipe)` to `recipe.archived_at = datetime.now(UTC)` + `self.database.db.commit()`. Follow the existing MealEvent soft-delete pattern from `delete_meal_event.py`.
  - [ ] Verify the endpoint still returns 200 with success response
  - [ ] Update existing tests in `services/api/tests/test_recipe.py` (`TestDeleteRecipe`) to verify the recipe is archived (not hard deleted)

- [ ] Task 2: Add archived_at filter to list endpoints (AC: #1)
  - [ ] In `services/api/src/api/v1/recipe/list_recipes.py`: add `.filter(Recipe.archived_at.is_(None))` to the query (line 52 area)
  - [ ] In `services/api/src/api/v1/recipe_book/list_recipe_books.py`: add `.filter(RecipeBook.archived_at.is_(None))` to the query
  - [ ] In `services/api/src/api/v1/recipe_book/get_recipe_book.py`: filter out archived recipes from the recipes list within the book detail
  - [ ] Verify `list_favorites.py` already filters (it does — `.filter(Recipe.archived_at.is_(None))`)
  - [ ] Verify search endpoint filters archived recipes — check `services/api/src/api/v1/search/search.py`

- [ ] Task 3: Create RestoreRecipe endpoint (AC: #4)
  - [ ] Create `services/api/src/api/v1/recipe/restore_recipe.py` — `RestoreRecipe(Endpoint)`, sets `recipe.archived_at = None`, commits. Verify recipe exists (including archived — use `self.database.find_by(Recipe, id=recipe_id, include_archived=True)`), verify ownership via RecipeBookUser with owner/editor role.
  - [ ] Register in `services/api/src/api/v1/recipe/__init__.py`
  - [ ] Add route `POST /v1/recipes/{recipe_id}/restore` in `services/api/src/routers/v1/recipe_router.py`
  - [ ] Add `restoreRecipe(String recipeId)` to Flutter `ApiClient`

- [ ] Task 4: Create ListArchivedRecipes endpoint (AC: #3)
  - [ ] Create `services/api/src/api/v1/recipe/list_archived_recipes.py` — `ListArchivedRecipes(Endpoint)`, GET `/v1/recipes/archived`. Query all recipes where `archived_at IS NOT NULL` across all recipe books the user has membership in. Return same RecipeItem format as ListRecipes plus `archived_at` datetime.
  - [ ] Register in `__init__.py` and recipe_router.py
  - [ ] Add `getArchivedRecipes()` to Flutter `ApiClient`

- [ ] Task 5: Add archive UI to Flutter RecipeDetailScreen and recipe cards (AC: #1)
  - [ ] RecipeDetailScreen: add archive option in a popup menu (3-dot menu or long-press). When user taps archive, show confirmation dialog, then call `deleteRecipe(recipeId)` (the existing delete method now archives). On success, pop back and show snackbar "Recipe archived".
  - [ ] HomeScreen RecipeCard `onLongPress`: currently calls `_quickStartCooking`. Add a bottom sheet with options: "Start Cooking" and "Archive". Archive option triggers confirmation + API call + reload.
  - [ ] RecipeBookDetailScreen: add swipe-to-archive on `_RecipeCard` or long-press menu with archive option.

- [ ] Task 6: Create Archive View screen in Flutter (AC: #3, #4)
  - [ ] Create `app/lib/features/recipes/archived_recipes_screen.dart` — screen showing grid/list of archived recipes fetched from `getArchivedRecipes()`. Each card shows recipe name, image, archived date.
  - [ ] Add restore button on each archived recipe card — calls `restoreRecipe()`, removes from list, shows snackbar "Recipe restored".
  - [ ] Add navigation to archive view from Profile/Settings screen or recipe books screen (gear icon or menu item "Archived Recipes").
  - [ ] Register route in `app/lib/core/router/app_router.dart` as `/recipes/archived`.

- [ ] Task 7: Backend and Flutter tests (AC: #1-#5)
  - [ ] Backend: Test archive (soft delete) via DELETE endpoint, test restore endpoint, test list archived, test archived recipes excluded from list/search, test restore preserves data
  - [ ] Verify existing delete tests still pass with soft-delete behavior

## Dev Notes

### Critical Context: This Is a Brownfield Story

**All recipe CRUD, favorites, and photo upload are COMPLETE** (Stories 2.1-2.4). The infrastructure for soft-delete (`archived_at` field on all models) has been present since the initial database migration but has not been wired up for recipes.

### Existing Soft-Delete Infrastructure (ALREADY IN PLACE)

**JoinsBase model** (`libraries/utils/utils/models/joins_base.py:20-26`):
```python
archived_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
def is_archived(self) -> bool:
    return self.archived_at is not None
```

**Database service** (`libraries/utils/utils/services/database.py:146-149`):
```python
# find_by() and where() both accept include_archived parameter
if not include_archived:
    query = query.filter(model.archived_at.is_(None))
```

**Key insight**: `self.database.find_by()` and `self.database.where()` ALREADY auto-filter archived records by default. This means endpoints that use these helpers already exclude archived records. BUT — endpoints that use raw `self.db.query()` (like `list_recipes.py`, `list_recipe_books.py`) do NOT filter and need manual `.filter(Model.archived_at.is_(None))`.

### Existing Soft-Delete Pattern to Follow

**MealEvent delete** (`services/api/src/api/v1/meal_event/delete_meal_event.py:43-45`):
```python
meal_event.archived_at = datetime.utcnow()
self.database.db.commit()
```

**Timer delete** (`services/api/src/api/v1/timer/delete_timer.py:43-46`):
```python
timer.status = "cancelled"
timer.archived_at = datetime.utcnow()
self.database.db.commit()
```

**Restore pattern** (`services/api/src/api/v1/invitations/helpers.py:217-220`):
```python
if existing.archived_at is not None:
    existing.archived_at = None
```

### Current Recipe Delete Implementation (HARD DELETE — Must Change)

**`delete_recipe.py`** currently does hard delete:
```python
self.database.delete(recipe)
```
This MUST change to soft delete (set `archived_at`). The API contract stays the same (DELETE /v1/recipes/{recipe_id}) — just the behavior changes from permanent deletion to archiving.

### Endpoints That Need archived_at Filtering

| Endpoint | File | Current Filter | Action |
|----------|------|----------------|--------|
| ListRecipes | `list_recipes.py:52` | No filter | Add `.filter(Recipe.archived_at.is_(None))` |
| ListRecipeBooks | `list_recipe_books.py` | No filter | Add `.filter(RecipeBook.archived_at.is_(None))` |
| GetRecipeBook (recipes list) | `get_recipe_book.py` | No filter on recipes | Add filter |
| ListFavorites | `list_favorites.py:34` | ✅ Already filters | No change |
| Search | `search.py` | Check needed | Add if missing |
| GetRecipe | `get_recipe.py` | Uses `self.database.find_by()` | ✅ Auto-filtered |

### RestoreRecipe Endpoint Design

```python
class RestoreRecipe(Endpoint):
    def execute(self, recipe_id: str):
        # IMPORTANT: Must use include_archived=True to find archived recipes
        recipe = self.database.find_by(Recipe, id=recipe_id, include_archived=True)
        if not recipe:
            raise APIException(404, "Recipe not found", ErrorCode.RECIPE_NOT_FOUND)
        if not recipe.is_archived():
            raise APIException(400, "Recipe is not archived", ErrorCode.RECIPE_NOT_ARCHIVED)
        # Check ownership
        membership = self.database.find_by(RecipeBookUser, user_id=str(user.id), recipe_book_id=recipe.recipe_book_id)
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(403, ...)
        recipe.archived_at = None
        self.database.db.commit()
        return success(data=RestoreRecipe.Response(id=str(recipe.id)))
```

**Error code**: May need a new `RECIPE_NOT_ARCHIVED = 112` in ErrorCode enum if it doesn't exist. Check `libraries/utils/utils/classes/error_code.py`.

### ListArchivedRecipes Endpoint Design

```python
class ListArchivedRecipes(Endpoint):
    def execute(self):
        # Get all recipe books user has access to
        # Query recipes where archived_at IS NOT NULL across those books
        # Return list with archived_at date included
```

### Flutter Archive View Design

Simple screen with a grid of archived recipe cards. Each card shows:
- Recipe image (or placeholder)
- Recipe name
- "Archived on {date}" subtitle
- Restore button (or swipe-to-restore)

Navigation: Add "Archived Recipes" option accessible from profile/settings or a menu on the recipe books screen.

### Learnings from Stories 2.1-2.4

- Use `Theme.of(context).colorScheme.*` for new screens
- `context.push()` for navigation with reload-on-return pattern
- User-friendly error messages (not raw `$e`)
- Always check `mounted` before `setState()` after async
- `HapticFeedback.selectionClick()` for toggle actions
- Optimistic UI with revert on failure
- Inflight guards (`_togglingFavoriteIds` pattern) to prevent double-tap race conditions
- Use `self.database.db.query()` (not `self.db.query()`) for raw queries — review feedback from Story 2.4
- Standardize `user_id=str(user.id)` in `find_by()` calls

### DO NOT:
- Add permanent/hard delete option — this story is about making delete = archive
- Add archive for recipe books — that's Story 2.8
- Add bulk archive — that's Story 2.7
- Add search within archive view — keep it simple, just a scrollable list
- Add version history preservation logic — versions don't exist yet (Epic 4)
- Create a new migration — `archived_at` column already exists on all tables

### References

- [Source: libraries/utils/utils/models/joins_base.py] — JoinsBase with archived_at field and is_archived()
- [Source: libraries/utils/utils/services/database.py] — Database service with include_archived parameter
- [Source: services/api/src/api/v1/recipe/delete_recipe.py] — Current hard delete (must change)
- [Source: services/api/src/api/v1/meal_event/delete_meal_event.py] — Soft delete pattern to follow
- [Source: services/api/src/api/v1/timer/delete_timer.py] — Another soft delete example
- [Source: services/api/src/api/v1/invitations/helpers.py] — Restore pattern (archived_at = None)
- [Source: services/api/src/api/v1/recipe/list_recipes.py] — Needs archived_at filter
- [Source: services/api/src/api/v1/recipe_book/list_recipe_books.py] — Needs archived_at filter
- [Source: services/api/src/api/v1/recipe_book/get_recipe_book.py] — Needs archived_at filter on recipes
- [Source: services/api/src/api/v1/recipe/list_favorites.py] — Already filters archived
- [Source: services/api/src/routers/v1/recipe_router.py] — Router registration
- [Source: services/api/src/api/v1/recipe/__init__.py] — Endpoint exports
- [Source: libraries/utils/utils/classes/error_code.py] — ErrorCode enum
- [Source: app/lib/core/services/api_client.dart] — Flutter API client
- [Source: app/lib/features/recipes/recipe_detail_screen.dart] — Detail screen (add archive action)
- [Source: app/lib/features/home/home_screen.dart] — Home screen (long-press menu)
- [Source: app/lib/features/recipe_books/recipe_book_detail_screen.dart] — Book detail (add archive action)
- [Source: services/api/tests/conftest.py] — Test fixtures
- [Source: services/api/tests/test_recipe.py] — Existing recipe tests

## Review Action Items

- [x] [AI-Review][HIGH] `archived_recipes_screen.dart:154-158`: Tapping archived recipe card navigates to `/recipes/${recipe['id']}`, but `GetRecipe` uses `find_by()` which auto-filters archived → 404. Remove onTap navigation from archived recipe cards (archive view is list-only per story scope). **Fixed**: Removed InkWell/onTap, replaced with Padding.
- [x] [AI-Review][MEDIUM] `recipe_detail_screen.dart:162-177`: Archive `PopupMenuButton` shown to ALL users including viewers. Should be conditional on `_recipe?['can_edit'] == true` to match the edit button guard. **Fixed**: Wrapped PopupMenuButton with `if (_recipe?['can_edit'] == true)`.
- [x] [AI-Review][MEDIUM] `home_screen.dart:_showRecipeActions` and `recipe_book_detail_screen.dart:onLongPress`: Archive action in long-press/bottom-sheet menus visible regardless of user role. API enforces access, but UX allows initiating a doomed action. **Fixed**: Added `can_edit != false` guards to archive options.
- [ ] [AI-Review][LOW] `delete_recipe.py:29`: Archiving an already-archived recipe yields misleading 404 "Recipe not found" (find_by auto-filters archived). Edge case — no real user impact. **Deferred**: No real user impact, would require changing find_by call pattern.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- Converted DeleteRecipe from hard delete to soft delete (archived_at)
- Added archived_at filter to list_recipes, list_recipe_books (recipe count), unified_search (both my + public)
- get_recipe_book uses self.database.where() which auto-filters; list_favorites already filters
- Created RestoreRecipe endpoint with include_archived=True, is_archived() check, ownership verification
- Created ListArchivedRecipes endpoint querying across all user's recipe books
- Added RECIPE_NOT_ARCHIVED error code (113)
- Added restoreRecipe() and getArchivedRecipes() to Flutter ApiClient
- Archive option added to RecipeDetailScreen (popup menu), HomeScreen (bottom sheet on long-press), RecipeBookDetailScreen (long-press)
- Created ArchivedRecipesScreen with list view, restore button, inflight guard
- Route registered at /recipes/archived (before /:id to avoid collision)
- Navigation from Profile screen "Archived Recipes" tile
- Added is_archived() to MockModel in conftest.py
- Tests: soft delete verification, restore (success, not found, not archived, no permission), list archived (empty, with results, auth required)

### File List

**New files:**
- `services/api/src/api/v1/recipe/restore_recipe.py` — RestoreRecipe endpoint
- `services/api/src/api/v1/recipe/list_archived_recipes.py` — ListArchivedRecipes endpoint
- `app/lib/features/recipes/archived_recipes_screen.dart` — Archive View screen

**Modified files:**
- `services/api/src/api/v1/recipe/delete_recipe.py` — Soft delete (archived_at) instead of hard delete
- `services/api/src/api/v1/recipe/list_recipes.py` — Added archived_at filter
- `services/api/src/api/v1/recipe_book/list_recipe_books.py` — Exclude archived recipes from count
- `services/api/src/api/v1/search/unified_search.py` — Filter archived from my + public recipe search
- `services/api/src/api/v1/recipe/__init__.py` — Added RestoreRecipe, ListArchivedRecipes exports
- `services/api/src/routers/v1/recipe_router.py` — Added restore + list archived routes
- `libraries/utils/utils/classes/error_code.py` — Added RECIPE_NOT_ARCHIVED = 113
- `app/lib/core/services/api_client.dart` — Added restoreRecipe(), getArchivedRecipes()
- `app/lib/features/recipes/recipe_detail_screen.dart` — Added archive popup menu
- `app/lib/features/home/home_screen.dart` — Added bottom sheet with archive option on long-press
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` — Added long-press archive
- `app/lib/core/router/app_router.dart` — Added /recipes/archived route
- `app/lib/features/profile/profile_screen.dart` — Added "Archived Recipes" navigation tile
- `services/api/tests/conftest.py` — Added is_archived() to MockModel
- `services/api/tests/test_recipe.py` — Added TestRestoreRecipe (4 tests), TestListArchivedRecipes (3 tests), updated TestDeleteRecipe
