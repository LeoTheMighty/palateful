# Story 2.6: Move & Copy Recipes Between Books

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to move or copy recipes between my personal books,
so that I can reorganize my collection as it grows.

## Acceptance Criteria

1. Given I own a recipe in one of my books, when I select "Move to...", then I can choose a destination book from my personal books
2. Given I select a destination book for move, then the recipe is removed from the source book and placed in the destination
3. Given I select "Copy to...", then I can choose a destination book and a duplicate is created in the destination while keeping the original
4. Given a move or copy operation completes, then the result is reflected immediately in both books

## Tasks / Subtasks

- [x] Task 1: Create MoveRecipe endpoint (AC: #1, #2)
  - [x] Create `services/api/src/api/v1/recipe/move_recipe.py` — `MoveRecipe(Endpoint)`, `POST /v1/recipes/{recipe_id}/move` with body `{destination_book_id}`. Verify recipe exists (non-archived), verify user has owner/editor role in BOTH source and destination books. Update `recipe.recipe_book_id` to destination book. Commit.
  - [x] Register in `services/api/src/api/v1/recipe/__init__.py`
  - [x] Add route `POST /recipes/{recipe_id}/move` in `services/api/src/routers/v1/recipe_router.py`
  - [x] Add `moveRecipe(String recipeId, String destinationBookId)` to Flutter `ApiClient`

- [x] Task 2: Create CopyRecipe endpoint (AC: #3)
  - [x] Create `services/api/src/api/v1/recipe/copy_recipe.py` — `CopyRecipe(Endpoint)`, `POST /v1/recipes/{recipe_id}/copy` with body `{destination_book_id}`. Verify recipe exists, verify user has access to source book (any role) AND owner/editor in destination. Clone recipe: create new Recipe with same fields but new `recipe_book_id`. Clone all RecipeIngredient rows (preserve `order_index`, `quantity_display`, `unit_display`, `quantity_normalized`, `unit_normalized`, `notes`, `is_optional`). Clone all RecipeStep rows (preserve all fields). Return new recipe ID.
  - [x] Register in `__init__.py` and `recipe_router.py`
  - [x] Add `copyRecipe(String recipeId, String destinationBookId)` to Flutter `ApiClient`

- [x] Task 3: Add Move/Copy UI to Flutter RecipeDetailScreen (AC: #1, #3)
  - [x] Add "Move to Book..." and "Copy to Book..." options to the existing `PopupMenuButton` in `recipe_detail_screen.dart` (inside the `can_edit` guard for move; copy can be available to all members)
  - [x] Create a book picker dialog/bottom sheet: fetch user's books via `getRecipeBooks()`, show list excluding the current book, user taps to select destination
  - [x] On move: call `moveRecipe()`, pop back to previous screen (recipe is no longer in source book), show snackbar "Recipe moved to {bookName}"
  - [x] On copy: call `copyRecipe()`, show snackbar "Recipe copied to {bookName}"

- [x] Task 4: Add Move/Copy to RecipeBookDetailScreen long-press menu (AC: #1, #3)
  - [x] In `recipe_book_detail_screen.dart`, change the long-press from directly calling `_archiveRecipe` to showing a bottom sheet with options: "Move to Book...", "Copy to Book...", "Archive"
  - [x] Reuse the book picker dialog from Task 3
  - [x] On move success: reload book (recipe removed from list)
  - [x] On copy success: show snackbar

- [x] Task 5: Backend and Flutter tests (AC: #1-#4)
  - [x] Backend: Test move (success, not found, no permission on source, no permission on destination, same book, dest not found)
  - [x] Backend: Test copy (success, not found, no access to source, no permission on destination)
  - [x] Verify existing recipe tests still pass (174 total, all passing)

## Dev Notes

### Critical Context: This Is a Brownfield Story

**All recipe CRUD, favorites, photos, and archive/restore are COMPLETE** (Stories 2.1-2.5). The Recipe model has a `recipe_book_id` FK that determines which book a recipe belongs to. Moving a recipe is simply updating this FK. Copying requires cloning the recipe and its child rows (ingredients, steps).

### Move Operation — Simple FK Update

Moving a recipe is a one-field update:
```python
recipe.recipe_book_id = destination_book_id
self.database.db.commit()
```

**Key considerations:**
- The `recipe_book_id` FK has `CASCADE` delete but that's for when the book is deleted, not relevant for moves
- No need to touch `RecipeIngredient` or `RecipeStep` — they reference `recipe.id` which doesn't change
- Favorites are preserved (they reference `recipe.id`, not the book)
- The recipe's `image_url` doesn't change (S3 URLs are standalone)
- Must verify user has owner/editor in BOTH source AND destination book

### Copy Operation — Clone Recipe + Children

Copying requires creating new database rows:

1. **Clone Recipe**: New `Recipe()` with all fields from source except `id` (auto-generated), `recipe_book_id` (set to destination), `created_at`/`updated_at` (auto-generated)
2. **Clone RecipeIngredient**: For each ingredient, create new `RecipeIngredient` with `recipe_id` pointing to the new recipe. Preserve `ingredient_id`, `quantity_display`, `unit_display`, `quantity_normalized`, `unit_normalized`, `notes`, `is_optional`, `order_index`.
3. **Clone RecipeStep**: For each step, create new `RecipeStep` with `recipe_id` pointing to the new recipe. Preserve `step_number`, `instruction`, `active_time_minutes`, `timers`, `wait_time_minutes`, `wait_type`, `can_prep_ahead`, `is_optional`.

**Key considerations:**
- Copy should be named like "Recipe Name" (no "Copy of" prefix — keep it clean, user can rename)
- `image_url` is copied as-is (same S3 URL, no re-upload needed)
- `embedding` vector should be copied too (same content, same embedding)
- For copy, user only needs read access to source (any membership role) but owner/editor in destination
- The copied recipe's `tags` list should be duplicated
- Do NOT copy `archived_at` — new copy should be active

### Endpoint Design

**MoveRecipe:**
```python
class MoveRecipe(Endpoint):
    class Params(BaseModel):
        destination_book_id: str

    class Response(BaseModel):
        id: str
        recipe_book_id: str

    def execute(self, recipe_id: str, params: "MoveRecipe.Params"):
        user: User = self.user
        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(404, "Recipe not found", ErrorCode.RECIPE_NOT_FOUND)

        # Check same book
        if str(recipe.recipe_book_id) == params.destination_book_id:
            raise APIException(400, "Recipe is already in this book", ErrorCode.INVALID_REQUEST)

        # Check source book access (owner/editor)
        src_membership = self.database.find_by(RecipeBookUser, user_id=str(user.id), recipe_book_id=recipe.recipe_book_id)
        if not src_membership or src_membership.role not in ("owner", "editor"):
            raise APIException(403, "...", ErrorCode.RECIPE_ACCESS_DENIED)

        # Check destination book exists and access (owner/editor)
        dest_book = self.database.find_by(RecipeBook, id=params.destination_book_id)
        if not dest_book:
            raise APIException(404, "Destination book not found", ErrorCode.RECIPE_BOOK_NOT_FOUND)
        dest_membership = self.database.find_by(RecipeBookUser, user_id=str(user.id), recipe_book_id=params.destination_book_id)
        if not dest_membership or dest_membership.role not in ("owner", "editor"):
            raise APIException(403, "...", ErrorCode.RECIPE_BOOK_ACCESS_DENIED)

        recipe.recipe_book_id = params.destination_book_id
        self.database.db.commit()
        return success(data=MoveRecipe.Response(id=str(recipe.id), recipe_book_id=str(recipe.recipe_book_id)))
```

**CopyRecipe:**
```python
class CopyRecipe(Endpoint):
    class Params(BaseModel):
        destination_book_id: str

    class Response(BaseModel):
        id: str

    def execute(self, recipe_id: str, params: "CopyRecipe.Params"):
        user: User = self.user
        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(404, "Recipe not found", ErrorCode.RECIPE_NOT_FOUND)

        # Check source access (any role — read access suffices for copy)
        src_membership = self.database.find_by(RecipeBookUser, user_id=str(user.id), recipe_book_id=recipe.recipe_book_id)
        if not src_membership:
            raise APIException(403, "...", ErrorCode.RECIPE_ACCESS_DENIED)

        # Check destination book exists and access (owner/editor)
        dest_book = self.database.find_by(RecipeBook, id=params.destination_book_id)
        if not dest_book:
            raise APIException(404, "Destination book not found", ErrorCode.RECIPE_BOOK_NOT_FOUND)
        dest_membership = self.database.find_by(RecipeBookUser, user_id=str(user.id), recipe_book_id=params.destination_book_id)
        if not dest_membership or dest_membership.role not in ("owner", "editor"):
            raise APIException(403, "...", ErrorCode.RECIPE_BOOK_ACCESS_DENIED)

        # Clone recipe
        new_recipe = Recipe(
            name=recipe.name,
            description=recipe.description,
            instructions=recipe.instructions,
            servings=recipe.servings,
            prep_time=recipe.prep_time,
            cook_time=recipe.cook_time,
            image_url=recipe.image_url,
            source_url=recipe.source_url,
            tags=list(recipe.tags) if recipe.tags else [],
            embedding=recipe.embedding,
            recipe_book_id=params.destination_book_id
        )
        self.database.create(new_recipe)
        self.database.db.refresh(new_recipe)

        # Clone ingredients
        source_ingredients = self.database.where(RecipeIngredient, recipe_id=str(recipe.id)).all()
        for ing in source_ingredients:
            new_ing = RecipeIngredient(
                recipe_id=new_recipe.id,
                ingredient_id=ing.ingredient_id,
                quantity_display=ing.quantity_display,
                unit_display=ing.unit_display,
                quantity_normalized=ing.quantity_normalized,
                unit_normalized=ing.unit_normalized,
                notes=ing.notes,
                is_optional=ing.is_optional,
                order_index=ing.order_index
            )
            self.database.create(new_ing)

        # Clone steps
        source_steps = self.database.where(RecipeStep, recipe_id=str(recipe.id)).all()
        for step in source_steps:
            new_step = RecipeStep(
                recipe_id=new_recipe.id,
                step_number=step.step_number,
                instruction=step.instruction,
                active_time_minutes=step.active_time_minutes,
                timers=step.timers,
                wait_time_minutes=step.wait_time_minutes,
                wait_type=step.wait_type,
                can_prep_ahead=step.can_prep_ahead,
                is_optional=step.is_optional,
            )
            self.database.create(new_step)

        return success(data=CopyRecipe.Response(id=str(new_recipe.id)), status=201)
```

### Flutter Book Picker UI

Create a reusable book picker bottom sheet:
```dart
Future<Map<String, dynamic>?> _showBookPicker({String? excludeBookId}) async {
  final response = await _apiClient.getRecipeBooks();
  final books = (response.data['items'] as List)
      .where((b) => b['id'] != excludeBookId)
      .toList();
  // Show bottom sheet with book list, return selected book or null
}
```

The picker should:
- Fetch books from API (already available via `getRecipeBooks()`)
- Exclude the current book from the list
- Show book name and recipe count
- Return selected book map or null if cancelled

### Learnings from Stories 2.1-2.5

- Use `Theme.of(context).colorScheme.*` for new screens
- `context.push()` for navigation with reload-on-return pattern
- User-friendly error messages (not raw `$e`)
- Always check `mounted` before `setState()` after async
- `HapticFeedback.selectionClick()` for action confirmations
- Use `self.database.db.query()` (not `self.db.query()`) for raw queries
- Standardize `user_id=str(user.id)` in `find_by()` calls
- Inflight guards to prevent double-tap race conditions
- `can_edit` guards on destructive/mutating UI actions
- Route ordering matters — literal paths before parameterized paths

### DO NOT:
- Add bulk move/copy — that's Story 2.7
- Add "Copy of" prefix to copied recipe names — keep clean
- Create a new migration — all needed columns already exist
- Add drag-and-drop reordering — out of scope
- Add cross-user move/copy — only within user's own books
- Hard-code book IDs or make assumptions about book count

### References

- [Source: libraries/utils/utils/models/recipe.py] — Recipe model with recipe_book_id FK
- [Source: libraries/utils/utils/models/recipe_book.py] — RecipeBook model
- [Source: libraries/utils/utils/models/recipe_book_user.py] — RecipeBookUser with role field
- [Source: libraries/utils/utils/models/recipe_ingredient.py] — RecipeIngredient join model
- [Source: libraries/utils/utils/models/recipe_step.py] — RecipeStep model
- [Source: services/api/src/api/v1/recipe/create_recipe.py] — CreateRecipe pattern to follow for copy cloning
- [Source: services/api/src/api/v1/recipe/delete_recipe.py] — Permission check pattern (membership + role)
- [Source: services/api/src/api/v1/recipe/restore_recipe.py] — Endpoint with include_archived pattern
- [Source: services/api/src/api/v1/recipe/__init__.py] — Endpoint exports
- [Source: services/api/src/routers/v1/recipe_router.py] — Router registration pattern
- [Source: libraries/utils/utils/classes/error_code.py] — ErrorCode enum (Recipe errors 110-119)
- [Source: libraries/utils/utils/services/database.py] — Database service (find_by, where, create)
- [Source: app/lib/core/services/api_client.dart] — Flutter API client
- [Source: app/lib/features/recipes/recipe_detail_screen.dart] — Detail screen popup menu (add move/copy)
- [Source: app/lib/features/recipe_books/recipe_book_detail_screen.dart] — Book detail (add long-press menu)
- [Source: services/api/tests/conftest.py] — Test fixtures and MockModel
- [Source: services/api/tests/test_recipe.py] — Existing recipe tests

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- Created MoveRecipe endpoint — updates `recipe.recipe_book_id` to destination book, validates owner/editor on both source and destination, rejects same-book moves
- Created CopyRecipe endpoint — clones Recipe with all fields (name, tags, embedding, image_url, etc.), clones all RecipeIngredient and RecipeStep rows, requires read access on source + owner/editor on destination
- Added `moveRecipe()` and `copyRecipe()` to Flutter ApiClient
- RecipeDetailScreen: expanded PopupMenuButton with "Move to Book...", "Copy to Book...", "Archive" — move/archive gated on `can_edit`, copy available to all members
- RecipeBookDetailScreen: changed long-press from direct archive to bottom sheet with move/copy/archive options, with `can_edit` guards
- Both screens share a `_showBookPicker` bottom sheet that fetches books and excludes current book
- Added TestMoveRecipe (6 tests) and TestCopyRecipe (5 tests) — all 175 tests pass

### Code Review Action Items

- [x] **MEDIUM**: Add inflight guards to `_moveRecipe()` and `_copyRecipe()` in both `recipe_detail_screen.dart` and `recipe_book_detail_screen.dart` to prevent double-tap race conditions (per dev notes learnings)
- [x] **MEDIUM**: Wrap book picker book list in scrollable constraint (`Flexible` + `ListView`) in both screens to prevent overflow with many books
- [x] **LOW**: Add `test_copy_recipe_dest_not_found` test to `TestCopyRecipe` (MoveRecipe has this test, CopyRecipe doesn't)
- [ ] **LOW**: `_showBookPicker` is duplicated across both screens — acceptable for now, candidate for extraction in a future story

### File List

**New files:**
- `services/api/src/api/v1/recipe/move_recipe.py` — MoveRecipe endpoint
- `services/api/src/api/v1/recipe/copy_recipe.py` — CopyRecipe endpoint

**Modified files:**
- `services/api/src/api/v1/recipe/__init__.py` — Added MoveRecipe, CopyRecipe exports
- `services/api/src/routers/v1/recipe_router.py` — Added move + copy routes
- `app/lib/core/services/api_client.dart` — Added moveRecipe(), copyRecipe()
- `app/lib/features/recipes/recipe_detail_screen.dart` — Added move/copy to popup menu + book picker
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` — Added bottom sheet with move/copy/archive + book picker
- `services/api/tests/test_recipe.py` — Added TestMoveRecipe (6 tests), TestCopyRecipe (4 tests)
