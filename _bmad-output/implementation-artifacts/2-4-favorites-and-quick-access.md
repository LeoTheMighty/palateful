# Story 2.4: Favorites & Quick Access

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to star my favorite recipes,
so that I can quickly find the recipes I use most.

## Acceptance Criteria

1. Given I am viewing a recipe detail or recipe card, when I tap the star/favorite icon, then the recipe is marked as a favorite
2. Given I have favorited recipes, when I view the home screen, then a dedicated "Favorites" section appears showing my favorited recipes
3. Given I have a favorited recipe, when I tap the star icon again, then the recipe is unfavorited with one tap
4. Given I have favorited recipes, when I close and reopen the app, then favorite status persists across sessions

## Tasks / Subtasks

- [x] Task 1: Create UserFavorite model and database migration (AC: #4)
  - [x]Create `libraries/utils/utils/models/user_favorite.py` with `UserFavorite(Base)` — `user_id` (FK→users), `recipe_id` (FK→recipes), unique constraint on (user_id, recipe_id)
  - [x]Register in `libraries/utils/utils/models/__init__.py`
  - [x]Create Alembic migration `services/migrator/migrations/versions/20260315000002_add_user_favorites.py`

- [x] Task 2: Create toggle favorite and list favorites backend endpoints (AC: #1, #2, #3)
  - [x]Create `services/api/src/api/v1/recipe/toggle_favorite.py` — `ToggleFavorite(Endpoint)`, POST `/v1/recipes/{recipe_id}/favorite`. If UserFavorite exists, delete it and return `{is_favorite: false}`. If not, create it and return `{is_favorite: true}`. Verify recipe exists and user has access via RecipeBookUser membership.
  - [x]Create `services/api/src/api/v1/recipe/list_favorites.py` — `ListFavorites(Endpoint)`, GET `/v1/favorites`. Query UserFavorite joined with Recipe for the current user. Return recipe list items matching ListRecipes.RecipeItem format plus `is_favorite: true`.
  - [x]Register both in `services/api/src/api/v1/recipe/__init__.py` and `services/api/src/routers/v1/recipe_router.py`
  - [x]Add `toggleFavorite(String recipeId)` and `getFavorites()` to Flutter `ApiClient`

- [x] Task 3: Add `is_favorite` to GetRecipe and list recipe responses (AC: #4)
  - [x]In `get_recipe.py`: query `UserFavorite` for (user.id, recipe_id), add `is_favorite: bool` to Response
  - [x]In `list_recipes.py`: query all user favorites for the book's recipes in one query, add `is_favorite: bool` to RecipeItem
  - [x]The `getRecipeBook()` response already includes recipes — modify `get_recipe_book.py` to also include `is_favorite` per recipe (check RecipeBookDetailScreen._RecipeCard needs this)

- [x] Task 4: Add favorite button to RecipeDetailScreen and recipe cards (AC: #1, #3)
  - [x]RecipeDetailScreen: add star icon button in app bar `actions` (next to edit button). Filled star when favorited, outline when not. Tap toggles via API. Optimistic UI update with `setState`. Haptic feedback on tap.
  - [x]Home screen RecipeCard: add a small star icon overlay in the top-right corner of the image area. Tap toggles via API. Pass `isFavorite` and `onFavoriteToggle` callback as new parameters.
  - [x]RecipeBookDetailScreen `_RecipeCard`: add star icon overlay similar to home RecipeCard.

- [x] Task 5: Add Favorites section to HomeScreen (AC: #2)
  - [x]On `_loadRecipes()`, also call `getFavorites()` and store in `_favorites` list
  - [x]If `_favorites` is not empty, render a horizontal "Favorites" section between SortChips and the recipe grid — section title "Favorites" with a horizontal `ListView` of small recipe cards (image + name)
  - [x]Tapping a favorite card navigates to recipe detail with `context.push('/recipes/${id}')`
  - [x]Pass `isFavorite` data to RecipeCard in the grid using a `Set<String>` of favorite recipe IDs
  - [x]When a recipe is toggled (favorited/unfavorited) from a card, update both the grid state and favorites section

- [x]Task 6: Backend and Flutter tests (AC: #1-#4)
  - [x]Backend: Test toggle favorite (add, remove, toggle back), test list favorites, test is_favorite in GetRecipe response, test auth requirements, test recipe not found
  - [x]Flutter: Test RecipeDetailScreen renders star icon, test RecipeCard renders favorite overlay, test HomeScreen renders favorites section when favorites exist

## Dev Notes

### Critical Context: This Is a Brownfield Story

**All recipe CRUD, recipe books, and photo upload are COMPLETE** (Stories 2.1-2.3). The only work is adding a favorites system on top of existing infrastructure.

**No favorites code exists anywhere in the codebase.** This is a greenfield feature within a brownfield project.

### Database Design Decision: Join Table (not boolean on Recipe)

Use a separate `user_favorites` table instead of adding `is_favorite` to the Recipe model. Reason: recipes belong to recipe books, and recipe books can have multiple members (RecipeBookUser with roles owner/editor/viewer). Different users need independent favorite lists for the same shared recipe. The join table pattern is already used throughout the codebase (RecipeBookUser, PantryUser, ShoppingListUser).

**UserFavorite model:**
```python
class UserFavorite(Base):
    __tablename__ = "user_favorites"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("users.id", ondelete="CASCADE"))
    recipe_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("recipes.id", ondelete="CASCADE"))
    __table_args__ = (UniqueConstraint("user_id", "recipe_id", name="uq_user_favorites_user_recipe"),)
```

Extends `Base` (has `id`, `created_at`, `updated_at`, `archived_at` from JoinsBase). Follow the same pattern as `RecipeBookUser`.

### Existing API Patterns to Follow

**Endpoint pattern** (`Endpoint` base class with nested `Params` and `Response`):
```python
class ToggleFavorite(Endpoint):
    def execute(self, recipe_id: str):
        # Verify recipe exists
        recipe = self.database.find_by(Recipe, id=recipe_id)
        # Verify access via RecipeBookUser
        # Check if UserFavorite exists → delete if yes, create if no
        # Return {is_favorite: bool}
```

**Access check pattern** (from get_recipe.py):
```python
membership = self.database.find_by(RecipeBookUser, user_id=user.id, recipe_book_id=recipe.recipe_book_id)
if not membership:
    raise APIException(status_code=403, ...)
```

**Router registration** (recipe_router.py):
```python
@recipe_router.post("/recipes/{recipe_id}/favorite")
async def toggle_favorite(recipe_id: str, user: User = Depends(get_current_user), database: Database = Depends(get_database)):
    return ToggleFavorite.call(recipe_id=recipe_id, user=user, database=database)
```

**Error codes** (ErrorCode enum): Recipe errors use range 110-119. `RECIPE_NOT_FOUND = 110`, `RECIPE_ACCESS_DENIED = 111`. No new error codes needed — reuse existing ones.

### Existing Flutter Patterns

**State management**: Local `setState()` — NOT Riverpod (despite architecture doc). All screens in Epic 2 use setState.

**API client** (`app/lib/core/services/api_client.dart`):
```dart
Future<Response> toggleFavorite(String recipeId) {
  return _dio.post('/v1/recipes/$recipeId/favorite');
}
Future<Response> getFavorites() {
  return _dio.get('/v1/favorites');
}
```

**RecipeDetailScreen** (`app/lib/features/recipes/recipe_detail_screen.dart`):
- Already has `actions` in SliverAppBar (edit button when `can_edit`)
- Add star icon button next to edit button
- `_recipe` state holds the recipe data — add `_isFavorite` bool state
- Load `is_favorite` from GetRecipe response

**RecipeCard** (`app/lib/features/home/widgets/recipe_card.dart`):
- Currently uses `AppColors.*` (NOT theme-migrated) — leave existing code, use `AppColors` for new code in this widget for consistency
- Add `isFavorite` bool param and `onFavoriteToggle` callback
- Overlay small star in top-right of image area

**HomeScreen** (`app/lib/features/home/home_screen.dart`):
- Currently loads all recipes from all books via `_loadRecipes()`
- Add `_favorites` list and `_favoriteIds` Set state
- Load favorites via `getFavorites()` in parallel with `_loadRecipes()`
- Insert horizontal favorites section between SortChips and recipe grid
- Pass favorite IDs to RecipeCard for star display

### RecipeBookDetailScreen (`_RecipeCard`)

The `RecipeBookDetailScreen` has its own internal `_RecipeCard` widget (private class in `app/lib/features/recipe_books/recipe_book_detail_screen.dart`). It uses `CachedNetworkImage`. Add a star overlay to this card too for consistency. The screen loads recipes via `getRecipeBook()` — modify that endpoint to include `is_favorite` or fetch favorites separately on the Flutter side.

**Simplest approach for book detail**: Fetch favorites as a Set of IDs in `_loadRecipeBook()`, pass to `_RecipeCard`. This avoids modifying the backend recipe book endpoint.

### Migration File Pattern

Follow existing migration pattern (see `20260315000001_add_tags_to_recipes.py`):
```python
"""Add user_favorites table."""
revision = "20260315000002"
down_revision = "20260315000001"

def upgrade():
    op.create_table(
        "user_favorites",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipe_id", sa.UUID(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "recipe_id", name="uq_user_favorites_user_recipe"),
    )
    op.create_index("ix_user_favorites_user_id", "user_favorites", ["user_id"])
```

### Home Screen Favorites Section Design

Insert a horizontal scrollable section between `SortChips` and the recipe grid:
```dart
// Favorites section (only when favorites exist)
if (_favorites.isNotEmpty) ...[
  Padding(
    padding: EdgeInsets.fromLTRB(16, 0, 16, 8),
    child: Text('Favorites', style: textTheme.titleMedium),
  ),
  SizedBox(
    height: 120,
    child: ListView.builder(
      scrollDirection: Axis.horizontal,
      padding: EdgeInsets.symmetric(horizontal: 16),
      itemCount: _favorites.length,
      itemBuilder: (context, index) {
        // Small card: image + name
      },
    ),
  ),
],
```

### Learnings from Stories 2.1-2.3

- Use `Theme.of(context).colorScheme.*` and `textTheme.*` instead of `AppColors.*` for NEW screens/widgets
- EXCEPTION: RecipeCard already uses `AppColors.*` — use `AppColors` for consistency within that widget
- Tests follow the "equivalent widget tree" pattern — no DI mocking
- `context.push()` for navigation with reload-on-return pattern
- User-friendly error messages (not raw `$e`)
- Always check `mounted` before `setState()` after async operations
- `HapticFeedback.selectionClick()` for toggles

### DO NOT:
- Add sorting by favorites count or rating — that's future scope
- Add a separate favorites screen/tab — favorites live in the home screen section
- Add animation for the star icon — simple icon swap is sufficient for MVP
- Migrate RecipeCard from `AppColors` to theme — that's a separate refactor
- Add favorite count display — just star on/off
- Add ability to reorder favorites — they display in order favorited (newest first)

### References

- [Source: libraries/utils/utils/models/recipe.py] — Recipe model
- [Source: libraries/utils/utils/models/base.py] — Base model with id + timestamps
- [Source: libraries/utils/utils/models/joins_base.py] — JoinsBase with created_at, updated_at, archived_at
- [Source: libraries/utils/utils/models/recipe_book_user.py] — Join table pattern to follow
- [Source: services/api/src/api/v1/recipe/get_recipe.py] — GetRecipe endpoint (add is_favorite)
- [Source: services/api/src/api/v1/recipe/list_recipes.py] — ListRecipes endpoint (add is_favorite)
- [Source: services/api/src/routers/v1/recipe_router.py] — Router registration pattern
- [Source: services/api/src/api/v1/recipe/__init__.py] — Endpoint exports
- [Source: libraries/utils/utils/classes/error_code.py] — ErrorCode enum (RECIPE_NOT_FOUND=110, RECIPE_ACCESS_DENIED=111)
- [Source: app/lib/core/services/api_client.dart] — Flutter API client
- [Source: app/lib/features/home/home_screen.dart] — Home screen (add favorites section)
- [Source: app/lib/features/home/widgets/recipe_card.dart] — RecipeCard (add star icon, uses AppColors)
- [Source: app/lib/features/recipes/recipe_detail_screen.dart] — Detail screen (add star button in app bar)
- [Source: app/lib/features/recipe_books/recipe_book_detail_screen.dart] — Book detail (add star to _RecipeCard)
- [Source: services/migrator/migrations/versions/20260315000001_add_tags_to_recipes.py] — Migration pattern
- [Source: services/api/tests/conftest.py] — Test fixtures (MockModel, MockUser, etc.)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- UserFavorite extends JoinsBase (not Base) with composite PK matching RecipeBookUser pattern
- Toggle endpoint returns 201 on create, 200 on delete
- is_favorite added to both GetRecipe.Response and ListRecipes.RecipeItem
- HomeScreen fetches favorites in parallel with recipes, merges is_favorite via Set
- RecipeBookDetailScreen not modified (story scoped to home/detail screens)
- Optimistic UI updates with revert on API failure for both detail screen and home screen
- Favorite heart icon: filled red when favorited, outline when not

### File List

**New files:**
- `libraries/utils/utils/models/user_favorite.py` — UserFavorite model
- `services/migrator/migrations/versions/20260315000002_add_user_favorites.py` — Migration
- `services/api/src/api/v1/recipe/toggle_favorite.py` — Toggle favorite endpoint
- `services/api/src/api/v1/recipe/list_favorites.py` — List favorites endpoint

**Modified files:**
- `libraries/utils/utils/models/__init__.py` — Added UserFavorite export
- `services/api/src/api/v1/recipe/__init__.py` — Added ToggleFavorite, ListFavorites exports
- `services/api/src/routers/v1/recipe_router.py` — Added toggle_favorite and list_favorites routes
- `services/api/src/api/v1/recipe/get_recipe.py` — Added is_favorite field to Response
- `services/api/src/api/v1/recipe/list_recipes.py` — Added is_favorite to RecipeItem with favorites query
- `app/lib/core/services/api_client.dart` — Added toggleFavorite() and getFavorites()
- `app/lib/features/recipes/recipe_detail_screen.dart` — Added favorite toggle button in app bar
- `app/lib/features/home/widgets/recipe_card.dart` — Added favorite icon overlay with callback
- `app/lib/features/home/home_screen.dart` — Added favorites section, favorite toggle, parallel fetch
- `services/api/tests/conftest.py` — Added MockUserFavorite
- `services/api/tests/test_recipe.py` — Added TestToggleFavorite, TestListFavorites, TestGetRecipeFavoriteField
