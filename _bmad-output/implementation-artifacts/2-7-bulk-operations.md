# Story 2.7: Bulk Operations

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to perform bulk actions on multiple recipes at once,
so that I can efficiently organize a large collection.

## Acceptance Criteria

1. Given I am browsing recipes in a book, when I enter multi-select mode (long press or select button), then I can select multiple recipes
2. Given I have selected multiple recipes, when I choose "Move to Book...", then all selected recipes are moved to the chosen destination book
3. Given I have selected multiple recipes, when I choose "Archive", then all selected recipes are archived
4. Given I have selected multiple recipes, when I choose "Add Tags", then I can add tags to all selected recipes at once
5. Given I have selected multiple recipes, when I choose "Remove Tags", then I can remove tags from all selected recipes at once
6. Given I am in multi-select mode, then a count of selected items is displayed and I can exit selection mode

## Tasks / Subtasks

- [x] Task 1: Create BulkMoveRecipes endpoint (AC: #2)
  - [x]Create `services/api/src/api/v1/recipe/bulk_move_recipes.py` — `BulkMoveRecipes(Endpoint)`, `POST /v1/recipes/bulk/move` with body `{recipe_ids: list[str], destination_book_id: str}`. For each recipe: verify exists (non-archived), verify user has owner/editor role in source book AND destination book. Update all `recipe.recipe_book_id` to destination. Return count of moved recipes.
  - [x]Register in `services/api/src/api/v1/recipe/__init__.py`
  - [x]Add route `POST /recipes/bulk/move` in `services/api/src/routers/v1/recipe_router.py` — **MUST be before `/recipes/{recipe_id}` routes**
  - [x]Add `bulkMoveRecipes(List<String> recipeIds, String destinationBookId)` to Flutter `ApiClient`

- [x] Task 2: Create BulkArchiveRecipes endpoint (AC: #3)
  - [x]Create `services/api/src/api/v1/recipe/bulk_archive_recipes.py` — `BulkArchiveRecipes(Endpoint)`, `POST /v1/recipes/bulk/archive` with body `{recipe_ids: list[str]}`. For each recipe: verify exists (non-archived), verify user has owner/editor in recipe's book. Set `archived_at = datetime.now(UTC)`. Return count of archived recipes.
  - [x]Register in `__init__.py` and `recipe_router.py`
  - [x]Add `bulkArchiveRecipes(List<String> recipeIds)` to Flutter `ApiClient`

- [x] Task 3: Create BulkUpdateTags endpoint (AC: #4, #5)
  - [x]Create `services/api/src/api/v1/recipe/bulk_update_tags.py` — `BulkUpdateTags(Endpoint)`, `POST /v1/recipes/bulk/tags` with body `{recipe_ids: list[str], add_tags: list[str], remove_tags: list[str]}`. For each recipe: verify exists (non-archived), verify user has owner/editor in recipe's book. Merge `add_tags` into existing tags (dedup), filter out `remove_tags`. Commit. Return count of updated recipes.
  - [x]Register in `__init__.py` and `recipe_router.py`
  - [x]Add `bulkUpdateTags(List<String> recipeIds, {List<String>? addTags, List<String>? removeTags})` to Flutter `ApiClient`

- [x] Task 4: Add multi-select mode to RecipeBookDetailScreen (AC: #1, #6)
  - [x]Add `_isSelectMode` boolean and `_selectedRecipeIds` Set<String> state
  - [x]Add AppBar select toggle button (e.g., `Icons.checklist` or `Icons.select_all`) to enter/exit select mode
  - [x]Long press on a recipe card enters select mode with that recipe pre-selected
  - [x]In select mode: tapping a recipe toggles selection (checkbox overlay on recipe cards), AppBar shows selected count "N selected", back button exits select mode
  - [x]In select mode: show bottom action bar with bulk action buttons: Move, Archive, Tags

- [x] Task 5: Implement bulk action handlers in RecipeBookDetailScreen (AC: #2, #3, #4, #5)
  - [x]"Move" action: show book picker (reuse `_showBookPicker`), call `bulkMoveRecipes()`, on success exit select mode and reload book
  - [x]"Archive" action: show confirmation dialog ("Archive N recipes?"), call `bulkArchiveRecipes()`, on success exit select mode and reload book
  - [x]"Tags" action: show tag input dialog with "Add Tags" / "Remove Tags" tabs or toggle, call `bulkUpdateTags()`, on success exit select mode and reload book
  - [x]All actions have inflight guards, haptic feedback, user-friendly error messages, mounted checks

- [x] Task 6: Backend and Flutter tests (AC: #1-#6)
  - [x]Backend: Test BulkMoveRecipes (success, empty list, no permission on source, no permission on destination, mixed permissions — partial success not allowed, dest not found)
  - [x]Backend: Test BulkArchiveRecipes (success, empty list, no permission, already archived recipe in list)
  - [x]Backend: Test BulkUpdateTags (success — add only, success — remove only, success — add and remove, empty list, no permission)
  - [x]Verify all existing tests still pass

## Dev Notes

### Critical Context: This Is a Brownfield Story

**All recipe CRUD, favorites, photos, archive/restore, and move/copy are COMPLETE** (Stories 2.1-2.6). The current codebase has 175 passing tests and 14 recipe endpoints. This story adds 3 bulk endpoints and a multi-select UI mode to the existing RecipeBookDetailScreen.

### Bulk Endpoint Design — All-or-Nothing Semantics

Each bulk endpoint should validate ALL recipes before performing ANY mutations. If any recipe fails validation (not found, no permission, wrong book), the entire operation should fail with a 400/403 error listing the first failing recipe. This prevents partial operations that leave the user confused about which recipes were affected.

**BulkMoveRecipes:**
```python
class BulkMoveRecipes(Endpoint):
    class Params(BaseModel):
        recipe_ids: list[str]
        destination_book_id: str

    class Response(BaseModel):
        moved_count: int

    def execute(self, params: "BulkMoveRecipes.Params"):
        user: User = self.user

        if not params.recipe_ids:
            raise APIException(400, "No recipes specified", ErrorCode.INVALID_REQUEST)

        # Validate destination book exists and user has editor/owner access
        dest_book = self.database.find_by(RecipeBook, id=params.destination_book_id)
        if not dest_book:
            raise APIException(404, "Destination book not found", ErrorCode.RECIPE_BOOK_NOT_FOUND)
        dest_membership = self.database.find_by(RecipeBookUser, user_id=str(user.id), recipe_book_id=params.destination_book_id)
        if not dest_membership or dest_membership.role not in ("owner", "editor"):
            raise APIException(403, "You don't have permission to add recipes to this book", ErrorCode.RECIPE_BOOK_ACCESS_DENIED)

        # Load and validate all recipes
        recipes = []
        for recipe_id in params.recipe_ids:
            recipe = self.database.find_by(Recipe, id=recipe_id)
            if not recipe:
                raise APIException(404, f"Recipe not found: {recipe_id}", ErrorCode.RECIPE_NOT_FOUND)
            if str(recipe.recipe_book_id) == params.destination_book_id:
                continue  # Skip recipes already in destination (idempotent)
            src_membership = self.database.find_by(RecipeBookUser, user_id=str(user.id), recipe_book_id=recipe.recipe_book_id)
            if not src_membership or src_membership.role not in ("owner", "editor"):
                raise APIException(403, "You don't have permission to move this recipe", ErrorCode.RECIPE_ACCESS_DENIED)
            recipes.append(recipe)

        # Perform moves
        for recipe in recipes:
            recipe.recipe_book_id = params.destination_book_id
        self.database.db.commit()

        return success(data=BulkMoveRecipes.Response(moved_count=len(recipes)))
```

**BulkArchiveRecipes:**
```python
class BulkArchiveRecipes(Endpoint):
    class Params(BaseModel):
        recipe_ids: list[str]

    class Response(BaseModel):
        archived_count: int

    def execute(self, params: "BulkArchiveRecipes.Params"):
        user: User = self.user

        if not params.recipe_ids:
            raise APIException(400, "No recipes specified", ErrorCode.INVALID_REQUEST)

        # Load and validate all recipes
        recipes = []
        for recipe_id in params.recipe_ids:
            recipe = self.database.find_by(Recipe, id=recipe_id)
            if not recipe:
                raise APIException(404, f"Recipe not found: {recipe_id}", ErrorCode.RECIPE_NOT_FOUND)
            membership = self.database.find_by(RecipeBookUser, user_id=str(user.id), recipe_book_id=recipe.recipe_book_id)
            if not membership or membership.role not in ("owner", "editor"):
                raise APIException(403, "You don't have permission to archive this recipe", ErrorCode.RECIPE_ACCESS_DENIED)
            recipes.append(recipe)

        # Perform archives
        now = datetime.now(UTC)
        for recipe in recipes:
            recipe.archived_at = now
        self.database.db.commit()

        return success(data=BulkArchiveRecipes.Response(archived_count=len(recipes)))
```

**BulkUpdateTags:**
```python
class BulkUpdateTags(Endpoint):
    class Params(BaseModel):
        recipe_ids: list[str]
        add_tags: list[str] = []
        remove_tags: list[str] = []

    class Response(BaseModel):
        updated_count: int

    def execute(self, params: "BulkUpdateTags.Params"):
        user: User = self.user

        if not params.recipe_ids:
            raise APIException(400, "No recipes specified", ErrorCode.INVALID_REQUEST)
        if not params.add_tags and not params.remove_tags:
            raise APIException(400, "No tag changes specified", ErrorCode.INVALID_REQUEST)

        # Load and validate all recipes
        recipes = []
        for recipe_id in params.recipe_ids:
            recipe = self.database.find_by(Recipe, id=recipe_id)
            if not recipe:
                raise APIException(404, f"Recipe not found: {recipe_id}", ErrorCode.RECIPE_NOT_FOUND)
            membership = self.database.find_by(RecipeBookUser, user_id=str(user.id), recipe_book_id=recipe.recipe_book_id)
            if not membership or membership.role not in ("owner", "editor"):
                raise APIException(403, "You don't have permission to edit this recipe", ErrorCode.RECIPE_ACCESS_DENIED)
            recipes.append(recipe)

        # Apply tag changes
        for recipe in recipes:
            current_tags = list(recipe.tags) if recipe.tags else []
            # Add new tags (deduplicate)
            for tag in params.add_tags:
                if tag not in current_tags:
                    current_tags.append(tag)
            # Remove tags
            current_tags = [t for t in current_tags if t not in params.remove_tags]
            recipe.tags = current_tags
        self.database.db.commit()

        return success(data=BulkUpdateTags.Response(updated_count=len(recipes)))
```

### Route Ordering — CRITICAL

Bulk routes use `/recipes/bulk/move`, `/recipes/bulk/archive`, `/recipes/bulk/tags`. These MUST be registered BEFORE the `/recipes/{recipe_id}` parameterized routes in `recipe_router.py`, otherwise FastAPI will interpret "bulk" as a `recipe_id`. Place them right after the `/recipes/archived` route (which follows the same "literal before parameterized" pattern).

### Flutter Multi-Select UI Design

**State Management:**
```dart
bool _isSelectMode = false;
final Set<String> _selectedRecipeIds = {};
bool _isBulkOperating = false;
```

**Entering Select Mode:**
- Long press on recipe card → enters select mode with that recipe pre-selected
- AppBar toggle button (checklist icon) → enters select mode with nothing selected

**Select Mode UI Changes:**
- AppBar: back arrow (exits select mode), title shows "{N} selected", actions show select-all toggle
- Recipe cards: show checkbox overlay (Checkbox widget in card corner), tap toggles selection instead of navigating
- Bottom: persistent bottom action bar with icon buttons: Move, Archive, Tags
- All items use `can_edit != false` gating — only editable recipes can be selected

**Exiting Select Mode:**
- Back button/arrow in AppBar
- After successful bulk operation
- `_selectedRecipeIds.clear()` + `setState(() => _isSelectMode = false)`

**Tag Input Dialog:**
A simple dialog with a text field to enter comma-separated tags, and a toggle between "Add" / "Remove" modes:
```dart
Future<void> _showBulkTagDialog() async {
  // Show dialog with TextField for tags (comma-separated)
  // Radio/toggle: Add Tags vs Remove Tags
  // On submit: call bulkUpdateTags with appropriate add_tags/remove_tags
}
```

### Learnings from Stories 2.1-2.6

- Use `Theme.of(context).colorScheme.*` for new UI elements
- `context.push()` for navigation with reload-on-return pattern
- User-friendly error messages (not raw `$e`)
- Always check `mounted` before `setState()` after async
- `HapticFeedback.selectionClick()` for action confirmations
- Use `self.database.db.commit()` after direct attribute mutations
- Standardize `user_id=str(user.id)` in `find_by()` calls
- Inflight guards (`_isBulkOperating`) to prevent double-tap race conditions
- `can_edit` guards on destructive/mutating UI actions
- Route ordering matters — literal paths before parameterized paths
- Book picker bottom sheet with `isScrollControlled: true` + `ConstrainedBox` for overflow safety
- `_showBookPicker` already exists in `recipe_book_detail_screen.dart` — reuse it directly

### DO NOT:
- Add bulk copy — that's beyond scope (copy creates new records which is heavyweight for bulk)
- Create new migrations — all needed columns/tables already exist
- Change the single-recipe move/archive/copy endpoints — they remain as-is
- Add drag-and-drop reordering — out of scope
- Add cross-user bulk operations — only within user's own books
- Add pagination to bulk operations — they operate on explicit recipe ID lists

### References

- [Source: libraries/utils/utils/models/recipe.py] — Recipe model with recipe_book_id FK, tags ARRAY field
- [Source: libraries/utils/utils/models/recipe_book.py] — RecipeBook model
- [Source: libraries/utils/utils/models/recipe_book_user.py] — RecipeBookUser with role field
- [Source: libraries/utils/utils/services/database.py] — Database service (find_by, where, create, update, db.commit())
- [Source: libraries/utils/utils/classes/error_code.py] — ErrorCode enum (Recipe errors 110-119)
- [Source: services/api/src/api/v1/recipe/move_recipe.py] — MoveRecipe pattern (permission checks, FK update)
- [Source: services/api/src/api/v1/recipe/delete_recipe.py] — DeleteRecipe pattern (archived_at set)
- [Source: services/api/src/api/v1/recipe/update_recipe.py] — UpdateRecipe pattern (tag updates via params.tags)
- [Source: services/api/src/api/v1/recipe/__init__.py] — Endpoint exports
- [Source: services/api/src/routers/v1/recipe_router.py] — Router registration pattern, route ordering
- [Source: app/lib/core/services/api_client.dart] — Flutter API client
- [Source: app/lib/features/recipe_books/recipe_book_detail_screen.dart] — Book detail screen (add multi-select mode here)
- [Source: services/api/tests/conftest.py] — Test fixtures and MockModel, MockDatabase
- [Source: services/api/tests/test_recipe.py] — Existing recipe tests (175 total)

## Code Review Action Items

### Review 1 — Adversarial Code Review (2026-03-15)

- [x] **MEDIUM — Dead code: `_showRecipeActions` method** (`recipe_book_detail_screen.dart:271-312`): This method was the old long-press handler showing single-recipe Move/Copy/Archive. Since long-press now enters select mode, it's never called. Remove it.

- [x] **MEDIUM — No upper limit on `recipe_ids` list size** (`bulk_move_recipes.py`, `bulk_archive_recipes.py`, `bulk_update_tags.py`): All three bulk endpoints accept unbounded `list[str]` for `recipe_ids`. A malicious or buggy client could send thousands of IDs causing O(n) DB lookups. Add `Field(max_length=100)` to the Pydantic Params.

- [x] **LOW — Missing test: bulk move idempotent skip**: `BulkMoveRecipes` has explicit logic to skip recipes already in the destination book (line 56-57) and return an adjusted `moved_count`, but this path has no test coverage.

- [ ] **LOW — Select mode available for viewer-role users**: The checklist icon in the AppBar shows when `_recipes.isNotEmpty` regardless of `can_edit` status. A viewer could enter select mode, select recipes, and attempt operations that will fail with 403. The API rejects correctly, but the UX is misleading. Deferring — viewer-role books are an edge case.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- Created BulkMoveRecipes endpoint — validates dest book + all recipes' source permissions, updates recipe_book_id for all, skips recipes already in dest (idempotent)
- Created BulkArchiveRecipes endpoint — validates all recipes exist + user has owner/editor, sets archived_at on all in one commit
- Created BulkUpdateTags endpoint — validates all recipes, merges add_tags (dedup) and filters out remove_tags from each recipe's tag array
- All 3 bulk routes registered before `{recipe_id}` parameterized routes to avoid path collision
- Added bulkMoveRecipes(), bulkArchiveRecipes(), bulkUpdateTags() to Flutter ApiClient
- RecipeBookDetailScreen: added multi-select mode with _isSelectMode, _selectedRecipeIds state
- AppBar: checklist icon enters select mode, close icon exits; title shows "{N} selected"; select-all/deselect-all toggle
- Long press enters select mode with recipe pre-selected; tap toggles selection in select mode
- Recipe cards show checkbox overlay and primary border when selected
- Bottom action bar with Move, Tags, Archive buttons (Archive in error color)
- Tag dialog with SegmentedButton for Add/Remove mode and comma-separated tag input
- All bulk actions have inflight guards (_isBulkOperating), haptic feedback, mounted checks, user-friendly errors
- FAB hidden in select mode
- Added TestBulkMoveRecipes (5 tests), TestBulkArchiveRecipes (4 tests), TestBulkUpdateTags (6 tests) — all 190 tests pass

### File List

**New files:**
- `services/api/src/api/v1/recipe/bulk_move_recipes.py` — BulkMoveRecipes endpoint
- `services/api/src/api/v1/recipe/bulk_archive_recipes.py` — BulkArchiveRecipes endpoint
- `services/api/src/api/v1/recipe/bulk_update_tags.py` — BulkUpdateTags endpoint

**Modified files:**
- `services/api/src/api/v1/recipe/__init__.py` — Added BulkMoveRecipes, BulkArchiveRecipes, BulkUpdateTags exports
- `services/api/src/routers/v1/recipe_router.py` — Added bulk/move, bulk/archive, bulk/tags routes
- `app/lib/core/services/api_client.dart` — Added bulkMoveRecipes(), bulkArchiveRecipes(), bulkUpdateTags()
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` — Added multi-select mode, bulk action handlers, _RecipeCard selection UI, _BulkActionButton widget
- `services/api/tests/test_recipe.py` — Added TestBulkMoveRecipes (5), TestBulkArchiveRecipes (4), TestBulkUpdateTags (6)
