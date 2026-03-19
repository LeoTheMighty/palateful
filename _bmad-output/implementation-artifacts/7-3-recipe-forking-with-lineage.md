# Story 7.3: Recipe Forking with Lineage

Status: done

## Story

As a user,
I want to fork a recipe from any book I have access to into my own book,
so that I can create my own version while preserving where it came from.

## Acceptance Criteria

1. **Given** I am viewing a recipe in a shared book (or any book I have access to) **When** I tap "Make My Copy" (fork) **Then** I see a personal book picker showing only books I own; I select a destination and a copy is created there as version 1.
2. **Given** a recipe is forked **When** I view it **Then** I see a lineage badge: "Forked from: [Recipe Name] ([Book Name])" below the description.
3. **Given** I edit a forked recipe **When** I change ingredients, steps, or title **Then** new versions are created on the fork (v2+) and the original recipe in the source book is untouched.
4. **Given** the source recipe is later archived **When** I view my forked recipe **Then** the lineage badge still shows the original recipe name and book name (preserved at fork time, not live-resolved).
5. **Given** I lose access to the source book **When** I view my forked recipe **Then** the lineage badge still shows (lineage is stored as snapshot fields on the recipe row, not foreign-key lookups at read time).

## Implementation Notes

### Backend — New Work Required

The `Recipe` model currently has NO fork/lineage fields. `copy_recipe.py` is a plain copy with no lineage. A dedicated fork endpoint must be built.

#### 1. Alembic Migration

File: `services/migrator/migrations/versions/20260319000004_add_recipe_fork_lineage.py`

Add four nullable columns to `recipes` table:
```python
op.add_column('recipes', sa.Column('forked_from_recipe_id', sa.UUID(), nullable=True))
op.add_column('recipes', sa.Column('forked_from_book_id', sa.UUID(), nullable=True))
op.add_column('recipes', sa.Column('forked_from_recipe_name', sa.String(), nullable=True))
op.add_column('recipes', sa.Column('forked_from_book_name', sa.String(), nullable=True))
```

No foreign key constraints — the source recipe/book may be archived or deleted. These are snapshot fields.

Downgrade: `op.drop_column(...)` for all four.

#### 2. Update Recipe Model

File: `libraries/utils/utils/models/recipe.py`

Add after `source_url`:
```python
forked_from_recipe_id: Mapped[uuid.UUID | None] = mapped_column(UUID, nullable=True)
forked_from_book_id: Mapped[uuid.UUID | None] = mapped_column(UUID, nullable=True)
forked_from_recipe_name: Mapped[str | None] = mapped_column(String, nullable=True)
forked_from_book_name: Mapped[str | None] = mapped_column(String, nullable=True)
```

Do NOT add ForeignKey constraints — these are preservation fields, not live FK references.

#### 3. New Endpoint: ForkRecipe

File: `services/api/src/api/v1/recipe/fork_recipe.py`

```python
class ForkRecipe(Endpoint):
    class Params(BaseModel):
        destination_book_id: str

    class Response(BaseModel):
        id: str
        forked_from_recipe_id: str
        forked_from_book_id: str
        forked_from_recipe_name: str
        forked_from_book_name: str
```

Logic:
1. Load source recipe by `recipe_id` → 404 if not found
2. Check caller has access to source book (any role) → 403 if not
3. Load destination book from `destination_book_id` → 404 if not found
4. Check caller is OWNER of destination book → 403 if not owner (`role != 'owner'`)
5. Load source book name: `self.database.find_by(RecipeBook, id=recipe.recipe_book_id)` → capture `.name`
6. Clone recipe row (same as `copy_recipe.py` but also set lineage fields):
   ```python
   new_recipe = Recipe(
       name=recipe.name, ...,
       recipe_book_id=params.destination_book_id,
       forked_from_recipe_id=recipe.id,
       forked_from_book_id=recipe.recipe_book_id,
       forked_from_recipe_name=recipe.name,
       forked_from_book_name=source_book.name,
   )
   ```
7. Clone all `RecipeIngredient` rows (same as `copy_recipe.py`)
8. Clone all `RecipeStep` rows (same as `copy_recipe.py`)
9. Return 201 with `ForkRecipe.Response`

**Route**: `POST /v1/recipes/{recipe_id}/fork`

#### 4. Update GetRecipe Response

File: `services/api/src/api/v1/recipe/get_recipe.py`

Add to `GetRecipe.Response`:
```python
forked_from_recipe_id: str | None = None
forked_from_book_id: str | None = None
forked_from_recipe_name: str | None = None
forked_from_book_name: str | None = None
```

Add to the `return success(data=GetRecipe.Response(...))` call:
```python
forked_from_recipe_id=str(recipe.forked_from_recipe_id) if recipe.forked_from_recipe_id else None,
forked_from_book_id=str(recipe.forked_from_book_id) if recipe.forked_from_book_id else None,
forked_from_recipe_name=recipe.forked_from_recipe_name,
forked_from_book_name=recipe.forked_from_book_name,
```

#### 5. Wire to Router

File: `services/api/src/api/v1/recipe/__init__.py` — add `ForkRecipe` import and to `__all__`

File: `services/api/src/routers/v1/recipe_router.py` — add route before the `POST /recipes/{recipe_id}/copy` route:
```python
@recipe_router.post("/recipes/{recipe_id}/fork", status_code=201)
async def fork_recipe(
    recipe_id: str,
    params: ForkRecipe.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Fork a recipe into a book you own, preserving lineage."""
    return ForkRecipe.call(recipe_id=recipe_id, params=params, user=user, database=database)
```

#### 6. Backend Tests

File: `services/api/tests/test_recipes.py` (append new class) OR new file `services/api/tests/test_fork_recipe.py`

```python
BOOK_ID = "b0000000-0000-0000-0000-000000000001"
DEST_BOOK_ID = "b0000000-0000-0000-0000-000000000002"

class TestForkRecipe:
    def test_fork_recipe_success(client, mock_db, mock_user):
        # Sets up recipe + source membership + dest ownership, asserts 201 + lineage fields
    def test_fork_recipe_no_source_access_returns_403(client, mock_db, mock_user):
        # Source membership lookup returns [] → 403
    def test_fork_recipe_dest_not_owner_returns_403(client, mock_db, mock_user):
        # Dest membership role='editor' → 403
    def test_fork_recipe_not_found_returns_404(client, mock_db, mock_user):
        # Recipe lookup returns [] → 404 or 500
```

Mock chain for `test_fork_recipe_success` (8 `db.execute` calls in order):
1. Fetch source recipe (`MockExecuteResult([recipe])`)
2. Source book membership check (`MockExecuteResult([src_membership])`)
3. Fetch destination book (`MockExecuteResult([dest_book])`)
4. Destination membership check (`MockExecuteResult([dest_membership])`) — role='owner'
5. Fetch source book for name (`MockExecuteResult([src_book])`)
6. Fetch source ingredients (`MockExecuteResult([])`) — no ingredients for simplicity
7. Fetch source steps (`MockExecuteResult([])`) — no steps for simplicity

Note: The `database.create(new_recipe)` calls go through `mock_db.db.add` / `mock_db.db.commit` — these are pre-stubbed in `MockDatabase`. Use `mock_db.db.refresh.side_effect = lambda obj: setattr(obj, 'id', uuid.uuid4())` to simulate the refresh.

Actually, looking at how `copy_recipe.py` works: it uses `self.database.find_by` (for single lookups) and `self.database.where(...).all()` (for lists of ingredients/steps). NOT `db.execute`. So the mock pattern is:

```python
mock_db.find_by.side_effect = [
    recipe,       # source recipe
    src_membership,  # source access check
    dest_book,    # destination book lookup
    dest_membership, # destination access check (role='owner')
    src_book,     # source book for name
]
mock_db.where.return_value.all.return_value = []  # no ingredients/steps
```

Check the `copy_recipe.py` — it uses `self.database.find_by` and `self.database.where`, NOT `db.execute`. ForkRecipe will follow the same pattern.

### Flutter — New Work Required

#### 7. ApiClient method

File: `app/lib/core/services/api_client.dart`

```dart
Future<Response> forkRecipe(String recipeId, String destinationBookId) =>
    _dio.post('/v1/recipes/$recipeId/fork',
        data: {'destination_book_id': destinationBookId});
```

#### 8. RecipeDetailScreen — Fork Flow + Lineage Badge

File: `app/lib/features/recipes/recipe_detail_screen.dart`

**a) Add `_forkRecipe()` method** (similar to `_copyRecipe()` but uses fork semantics):

```dart
Future<void> _forkRecipe() async {
  if (_isMovingOrCopying) return;
  final currentBookId = _recipe?['recipe_book_id']?.toString();
  // Show book picker filtered to owned books only
  final book = await _showOwnedBookPicker(excludeBookId: currentBookId);
  if (book == null) return;

  setState(() => _isMovingOrCopying = true);
  final messenger = ScaffoldMessenger.of(context);
  final nav = context as NavigatorState?; // capture before async
  try {
    HapticFeedback.selectionClick();
    final response = await _apiClient.forkRecipe(
        widget.recipeId, book['id'].toString());
    final forkedId = response.data['id'] as String?;
    if (mounted && forkedId != null) {
      messenger.showSnackBar(
        SnackBar(content: Text('Forked to ${book['name']}')),
      );
      context.push('/recipes/$forkedId');
    }
  } catch (e) {
    if (mounted) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Could not fork recipe. Please try again.')),
      );
    }
  } finally {
    if (mounted) setState(() => _isMovingOrCopying = false);
  }
}
```

**b) Add `_showOwnedBookPicker()` method** — like `_showBookPicker()` but filters books where user is owner:

```dart
Future<Map<String, dynamic>?> _showOwnedBookPicker({String? excludeBookId}) async {
  try {
    final response = await _apiClient.getRecipeBooks();
    final books = ((response.data['items'] as List?) ?? [])
        .where((b) =>
            b['id']?.toString() != excludeBookId &&
            b['user_role'] == 'owner')  // only owned books
        .toList();

    if (!mounted) return null;
    if (books.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No personal books available to fork into')),
      );
      return null;
    }

    return showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      builder: (context) => ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.6),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: Text('Fork into...', style: Theme.of(context).textTheme.titleMedium),
              ),
              Flexible(
                child: ListView(
                  shrinkWrap: true,
                  children: books.map((book) => ListTile(
                    leading: const Icon(Icons.menu_book_outlined),
                    title: Text(book['name'] ?? 'Untitled'),
                    subtitle: Text('${book['recipe_count'] ?? 0} recipes'),
                    onTap: () => Navigator.pop(context, book),
                  )).toList(),
                ),
              ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  } catch (e) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not load books. Please try again.')),
      );
    }
    return null;
  }
}
```

**IMPORTANT**: Check what field `getRecipeBooks()` returns for user's role in a book. Look at the existing ListRecipeBooks endpoint to find the role field name. It may be `user_role` or `role`. Adjust the filter accordingly.

**c) Add "Make My Copy" to PopupMenuButton** — add after the existing `copy` menu item, always visible:

```dart
const PopupMenuItem(
  value: 'fork',
  child: Row(
    children: [
      Icon(Icons.call_split_outlined),
      SizedBox(width: 8),
      Text('Make My Copy'),
    ],
  ),
),
```

In the `onSelected` handler:
```dart
} else if (value == 'fork') {
  _forkRecipe();
}
```

**d) Lineage badge** — add in the `SliverPadding` content section, right after description:

```dart
if (_recipe?['forked_from_recipe_name'] != null) ...[
  Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    decoration: BoxDecoration(
      color: colorScheme.secondaryContainer,
      borderRadius: BorderRadius.circular(8),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.call_split_outlined, size: 14, color: colorScheme.onSecondaryContainer),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            'Forked from: ${_recipe!['forked_from_recipe_name']} (${_recipe!['forked_from_book_name'] ?? 'unknown book'})',
            style: textTheme.labelSmall?.copyWith(color: colorScheme.onSecondaryContainer),
          ),
        ),
      ],
    ),
  ),
  const SizedBox(height: 12),
],
```

Place this BEFORE the description block (lines ~385-394 in current file).

#### 9. Flutter Widget Tests

File: `app/test/features/recipes/fork_recipe_test.dart` (new file)

Tests (UI isolation style — no GetIt required, just widget scaffolding):
- Shows lineage badge when `forked_from_recipe_name` is non-null
- Lineage badge absent when `forked_from_recipe_name` is null
- "Make My Copy" menu item appears in popup menu

## Tasks / Subtasks

- [x] Task 1: Alembic migration — add fork lineage columns (AC: #4, #5)
  - [x] Create `services/migrator/migrations/versions/20260319000004_add_recipe_fork_lineage.py`
  - [x] Add `forked_from_recipe_id`, `forked_from_book_id`, `forked_from_recipe_name`, `forked_from_book_name` columns to `recipes` — all nullable, no FK constraints
  - [x] Include downgrade (drop columns)

- [x] Task 2: Update Recipe model (AC: #4, #5)
  - [x] Add four nullable fields to `libraries/utils/utils/models/recipe.py` (no FK constraints)

- [x] Task 3: Implement ForkRecipe endpoint (AC: #1, #2, #4, #5)
  - [x] Create `services/api/src/api/v1/recipe/fork_recipe.py`
  - [x] Clone recipe + ingredients + steps (reuse pattern from `copy_recipe.py`)
  - [x] Set all four lineage fields from source recipe and book at fork time
  - [x] Validate: source access (any role), destination access (owner only)
  - [x] Add import to `services/api/src/api/v1/recipe/__init__.py`
  - [x] Add route to `services/api/src/routers/v1/recipe_router.py`

- [x] Task 4: Update GetRecipe response with lineage fields (AC: #2, #4, #5)
  - [x] Add `forked_from_*` fields to `GetRecipe.Response`
  - [x] Populate them in `GetRecipe.execute()`

- [x] Task 5: Backend tests (AC: #1, #3, #4, #5)
  - [x] Add `TestForkRecipe` class with 4 tests to `services/api/tests/test_fork_recipe.py`
  - [x] Test success: verify 201 + lineage fields in response
  - [x] Test no source access: 403
  - [x] Test destination not owner: 403
  - [x] Test source not found: 404
  - [x] Run `npx nx run api:test` — 259 tests pass (added dest_no_membership test + 2 GetRecipe lineage tests)

- [x] Task 6: Flutter — ApiClient.forkRecipe() (AC: #1)
  - [x] Add `forkRecipe(recipeId, destinationBookId)` to `app/lib/core/services/api_client.dart`

- [x] Task 7: Flutter — RecipeDetailScreen fork flow + lineage badge (AC: #1, #2)
  - [x] Add `_forkRecipe()` method
  - [x] Add `_showOwnedBookPicker()` method (filters books by `user_role == 'owner'`)
  - [x] Confirmed `user_role` field name from `ListRecipeBooks` response
  - [x] Add "Make My Copy" `PopupMenuItem` with `Icons.call_split_outlined`
  - [x] Add lineage badge in content section (when `forked_from_recipe_name != null`)
  - [x] Navigate to new forked recipe on success

- [x] Task 8: Flutter widget tests (AC: #2)
  - [x] Create `app/test/features/recipes/fork_recipe_test.dart`
  - [x] Test: lineage badge renders when forked_from_recipe_name is set
  - [x] Test: no badge when no lineage
  - [x] Test: "Make My Copy" appears in popup items
  - [x] Run `flutter test` — 156 tests pass

### Code Review Fixes Applied
- Added `test_fork_recipe_dest_no_membership_returns_403` — covers `dest_membership=None` branch
- Added `test_get_recipe_returns_lineage_fields_for_forked_recipe` — verifies GetRecipe returns lineage fields for forked recipes
- Added `test_get_recipe_lineage_fields_null_for_non_forked` — verifies null lineage on non-forked recipes
- Fixed `_forkRecipe()` to use `book['id']` not `book['id'].toString()` (consistent with `_copyRecipe`)
- Added `services/api/tests/conftest.py` to File List (was missing — modified to add lineage fields to MockRecipe)

## Dev Notes

### Architecture Compliance
- Follow `Endpoint` class pattern with nested `Params` and `Response` (mandatory per architecture)
- Use `success()` helper for all API responses (mandatory)
- Alembic migration required — NEVER raw SQL on schema changes
- Test in `services/api/tests/` following `TestClassName.test_method_name` pattern
- No FK constraints on lineage columns — preservation semantics, not referential integrity

### Copy Pattern Reference
The `ForkRecipe` endpoint is structurally identical to `copy_recipe.py` PLUS:
1. Validates destination is OWNER (not just owner/editor)
2. Fetches source book name before cloning
3. Sets the four lineage fields on the cloned recipe

Follow `copy_recipe.py` exactly for the clone logic (ingredients + steps loops). Do NOT add FK constraint to `forked_from_recipe_id` or `forked_from_book_id`.

### Field Name for User Role in Book List
Before implementing `_showOwnedBookPicker`, check `services/api/src/api/v1/recipe_book/list_recipe_books.py` for the field name returned per book item for the user's role. It may be `user_role` or `role`. Use the correct field name in the Flutter filter.

### use_build_context_synchronously Pattern
In `_forkRecipe()`, pre-capture `ScaffoldMessenger.of(context)` BEFORE the `await _apiClient.forkRecipe(...)` call to avoid lint warnings (same pattern applied in Story 7.2's code review fixes).

### Migration Naming
Latest migration: `20260319000003_add_is_shared_to_recipe_books.py`
Next filename: `20260319000004_add_recipe_fork_lineage.py`

### MockRecipe in Tests
`MockRecipe` in `conftest.py` does NOT have `forked_from_*` fields yet. After adding them to the model, the mock constructor will accept kwargs gracefully (it uses `defaults.update(kwargs)` pattern). For the fork endpoint test, set these on the returned new recipe via `mock_db.db.refresh.side_effect`.

### Project Structure References
- Backend endpoint: `services/api/src/api/v1/recipe/fork_recipe.py`
- Backend init: `services/api/src/api/v1/recipe/__init__.py`
- Backend router: `services/api/src/routers/v1/recipe_router.py`
- Backend tests: `services/api/tests/test_recipes.py` or `test_fork_recipe.py`
- Flutter screen: `app/lib/features/recipes/recipe_detail_screen.dart`
- Flutter API client: `app/lib/core/services/api_client.dart`
- Flutter tests: `app/test/features/recipes/fork_recipe_test.dart`
- Model: `libraries/utils/utils/models/recipe.py`
- Migration: `services/migrator/migrations/versions/20260319000004_add_recipe_fork_lineage.py`

### References
- Existing copy pattern: `services/api/src/api/v1/recipe/copy_recipe.py`
- GetRecipe response structure: `services/api/src/api/v1/recipe/get_recipe.py`
- Recipe model: `libraries/utils/utils/models/recipe.py`
- RecipeDetailScreen: `app/lib/features/recipes/recipe_detail_screen.dart` (existing move/copy/book picker pattern)
- Story 7.2 (previous): `_bmad-output/implementation-artifacts/7-2-invitation-system.md` — use_build_context_synchronously fix pattern

## QA Walkthrough

**Happy paths:**
1. Open a recipe in a shared book as viewer → tap ⋮ menu → tap "Make My Copy" → see owned-books picker → select personal book → verify success snackbar + navigation to new recipe
2. Open the forked recipe → verify "Forked from: [Original Name] ([Book Name])" badge appears
3. Edit the forked recipe (change title or ingredient) → verify version count increments → verify original recipe in source book is unchanged
4. Archive the source recipe → return to forked recipe → verify lineage badge still shows original name

**Edge cases:**
- User has no owned books → verify "No personal books available to fork into" snackbar
- Fork recipe you already own → the fork should still succeed (no ownership gate on source)
- Fork into a shared book where you're editor (not owner) → backend returns 403 → Flutter shows error snackbar

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Migration `20260319000004_add_recipe_fork_lineage.py` adds 4 nullable columns with no FK constraints
- `ForkRecipe` endpoint follows `CopyRecipe` pattern exactly, adding lineage snapshot fields and owner-only destination check
- `MockRecipe` in `conftest.py` updated to include the 4 new lineage fields (defaulting to None) to fix GetRecipe tests
- `user_role` is the correct field name for the user's role in `getRecipeBooks()` items (confirmed from `ListRecipeBooks` response)
- `ScaffoldMessenger.of(context)` pre-captured before `await _showOwnedBookPicker()` to avoid `use_build_context_synchronously` lint
- Flutter analyze shows 0 issues from new/modified files

### File List

- `services/migrator/migrations/versions/20260319000004_add_recipe_fork_lineage.py` — new migration
- `libraries/utils/utils/models/recipe.py` — add four lineage columns
- `services/api/src/api/v1/recipe/fork_recipe.py` — new endpoint
- `services/api/src/api/v1/recipe/__init__.py` — add ForkRecipe import
- `services/api/src/routers/v1/recipe_router.py` — add fork route
- `services/api/src/api/v1/recipe/get_recipe.py` — add lineage fields to response
- `services/api/tests/test_recipes.py` (or `test_fork_recipe.py`) — TestForkRecipe class
- `app/lib/core/services/api_client.dart` — add forkRecipe() method
- `app/lib/features/recipes/recipe_detail_screen.dart` — fork flow + lineage badge
- `app/test/features/recipes/fork_recipe_test.dart` — new widget tests
- `services/api/tests/conftest.py` — MockRecipe updated with forked_from_* fields
