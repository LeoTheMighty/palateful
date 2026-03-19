# Story 8.2: Add Recipe Ingredients to Shopping List

Status: review

## Story

As a user,
I want to add all ingredients from a recipe directly to my shopping list with one tap,
So that I don't have to manually type each ingredient when planning a meal.

## Acceptance Criteria

1. **Given** I am viewing a recipe detail screen, **When** I tap "Add to Cart" (from the recipe actions menu), **Then** all non-archived ingredients from the recipe are added to my selected shopping list.

2. **Given** I have multiple shopping lists, **When** I tap "Add to Cart", **Then** I see a list picker bottom sheet showing all my active lists, and I can choose which one to add to.

3. **Given** I have exactly one shopping list, **When** I tap "Add to Cart", **Then** ingredients are added to that list automatically (no picker needed).

4. **Given** I have no shopping lists, **When** I tap "Add to Cart", **Then** I see a snackbar message directing me to create a list first ("No shopping lists — tap + to create one").

5. **Given** ingredients are added successfully, **Then** a snackbar confirms: "Added N ingredient(s) to [List Name]" (singular for 1 item).

6. **Given** an ingredient already exists in the list from the same recipe (same `ingredient_id` + `recipe_id`), **Then** that ingredient is skipped (not duplicated) and counted in `items_skipped`.

7. **Given** my partner is also viewing the same shopping list, **When** I add recipe ingredients, **Then** each added item appears on their screen within 1 second (real-time WebSocket broadcast per item).

8. **Given** items are added, **Then** each item retains its source attribution: `recipe_id` links back to the recipe, `name` = ingredient canonical name, `quantity` + `unit` from recipe display values, `category` from ingredient.

## Tasks / Subtasks

- [x] Task 1: Backend — `PopulateFromRecipe` endpoint (AC: 1, 6, 8)
  - [x] 1.1 Create `services/api/src/api/v1/shopping_list/populate_from_recipe.py`
  - [x] 1.2 Implement `PopulateFromRecipe(Endpoint)` class with `execute(list_id, params)`:
    - Fetch recipe by `params.recipe_id`; 404 if not found
    - Verify user can view recipe: `database.find_by(RecipeBookUser, user_id=user.id, recipe_book_id=recipe.recipe_book_id)` — 403 if None
    - Fetch shopping list by `list_id`; 404 if not found
    - Verify user can edit shopping list: owner OR `ShoppingListUser` with role `owner`/`editor` — 403 if not
    - Build `existing_keys` set: `{(item.ingredient_id, item.recipe_id) for item in shopping_list.items if item.archived_at is None}`
    - For each `recipe_ingredient` in `recipe.ingredients` (skip if `archived_at` is not None):
      - Access `ingredient = recipe_ingredient.ingredient`; skip if None
      - Check `(ingredient.id, recipe.id)` in `existing_keys` → skip and increment `items_skipped`
      - Create `ShoppingListItem(shopping_list_id=shopping_list.id, name=ingredient.canonical_name, quantity=recipe_ingredient.quantity_display, unit=recipe_ingredient.unit_display, category=ingredient.category, ingredient_id=ingredient.id, recipe_id=recipe.id, added_by_user_id=user.id)`
      - `database.create(item)` + `database.db.refresh(item)` + append to `added_items`
    - `database.db.commit()`
    - Return `success(data=PopulateFromRecipe.Response(items_added=..., items_skipped=..., items=[...]))`
  - [x] 1.3 Define `Params(BaseModel)` with `recipe_id: str`
  - [x] 1.4 Define inner `ItemResponse(BaseModel)` matching `AddShoppingListItem.Response` fields (id, name, quantity, unit, is_checked, category, ingredient_id, recipe_id, created_at, updated_at)
  - [x] 1.5 Define `Response(BaseModel)` with `items_added: int`, `items_skipped: int`, `items: list[ItemResponse]`

- [x] Task 2: Backend — Export and router wiring (AC: 1, 7)
  - [x] 2.1 In `services/api/src/api/v1/shopping_list/__init__.py`, add `from .populate_from_recipe import PopulateFromRecipe` and add to `__all__`
  - [x] 2.2 In `services/api/src/routers/v1/shopping_list_router.py`, import `PopulateFromRecipe` and add route:
    ```python
    @shopping_list_router.post("/shopping-lists/{list_id}/populate-from-recipe")
    async def populate_shopping_list_from_recipe(
        list_id: str,
        params: PopulateFromRecipe.Params,
        user: User = Depends(get_current_user),
        database: Database = Depends(get_database),
    ):
        result = PopulateFromRecipe.call(list_id=list_id, params=params, user=user, database=database)
        response_data = json.loads(result.body)
        for item in response_data.get("items", []):
            await broadcast_event_to_list(list_id, "item_added", item, user_id=str(user.id))
        return result
    ```

- [x] Task 3: Flutter — API client method (AC: 1)
  - [x] 3.1 In `app/lib/core/services/api_client.dart`, add method:
    ```dart
    Future<Response> populateShoppingListFromRecipe(String listId, Map<String, dynamic> data) =>
        _dio.post('/v1/shopping-lists/$listId/populate-from-recipe', data: data);
    ```

- [x] Task 4: Flutter — ShoppingCartService method (AC: 1, 5)
  - [x] 4.1 In `app/lib/features/shopping_cart/services/shopping_cart_service.dart`, add `populateFromRecipe()`:
    ```dart
    Future<({int itemsAdded, int itemsSkipped, String listName})> populateFromRecipe(
      String listId,
      String recipeId,
    ) async {
      final response = await _apiClient.populateShoppingListFromRecipe(listId, {'recipe_id': recipeId});
      final data = response.data as Map<String, dynamic>;
      return (
        itemsAdded: data['items_added'] as int,
        itemsSkipped: data['items_skipped'] as int,
        listName: '',  // caller supplies list name from their state
      );
    }
    ```
    Note: Return a simple record with `itemsAdded` and `itemsSkipped`. The caller (recipe_detail_screen) already knows the list name from the picker.

- [x] Task 5: Flutter — Add to Cart action in RecipeDetailScreen (AC: 1, 2, 3, 4, 5)
  - [x] 5.1 In `app/lib/features/recipes/recipe_detail_screen.dart`, add `_addIngredientsToCart()` method:
    - Get `ShoppingCartService` from `getIt<ShoppingCartService>()`
    - Call `service.getShoppingLists()` to fetch user's lists
    - If empty: `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No shopping lists — tap + to create one')))`; return
    - If exactly one list: use it directly
    - If multiple lists: show `showModalBottomSheet` with `ListView` of list names; user picks one
    - Call `service.populateFromRecipe(selectedList.id, recipeId)` — wrap in try/catch
    - On success: `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Added ${result.itemsAdded} ingredient${result.itemsAdded == 1 ? '' : 's'} to ${selectedList.name}')))`
    - On error: show generic error snackbar
  - [x] 5.2 Add "Add to Cart" option to existing `PopupMenuButton` in `recipe_detail_screen.dart` (before other actions):
    ```dart
    const PopupMenuItem(
      value: 'add_to_cart',
      child: Row(children: [
        Icon(Icons.shopping_cart_outlined),
        SizedBox(width: 8),
        Text('Add to Cart'),
      ]),
    ),
    ```
  - [x] 5.3 In `PopupMenuButton.onSelected`, handle `'add_to_cart'` → call `_addIngredientsToCart()`

- [x] Task 6: Backend — Tests (AC: 1, 6, 7, 8)
  - [x] 6.1 Create `services/api/tests/test_populate_from_recipe.py` covering:
    - `test_populate_from_recipe_success` — adds N items, returns correct `items_added`
    - `test_populate_from_recipe_skips_duplicates` — when same `(ingredient_id, recipe_id)` exists, `items_skipped` increments
    - `test_populate_from_recipe_skips_archived_ingredients` — archived recipe ingredients are not added
    - `test_populate_from_recipe_404_recipe` — 404 when recipe not found
    - `test_populate_from_recipe_403_no_recipe_access` — 403 when user not in recipe book
    - `test_populate_from_recipe_403_no_list_access` — 403 when user not editor of shopping list
    - `test_populate_from_recipe_broadcasts_each_item` — router broadcasts `item_added` for each added item
  - [x] 6.2 305 backend tests pass (10 new tests added, all existing pass)

- [x] Task 7: Flutter — Tests (AC: 1, 2, 3, 4, 5)
  - [x] 7.1 Create `app/test/features/recipes/add_to_cart_test.dart` with widget tests: popup menu item existence, no-lists snackbar, success snackbar (singular/plural), fallback list name, list picker bottom sheet
  - [x] 7.2 All existing Flutter tests continue to pass

## Dev Notes

### Backend: `PopulateFromRecipe` Endpoint Pattern

Follow `generate_from_meal_event.py` as the primary reference — it does exactly what we need: iterate recipe ingredients, create `ShoppingListItem` objects, return a summary. Our version is simpler since we don't create a new shopping list (we add to an existing one).

**Key model details:**
- `RecipeIngredient`: composite PK `(recipe_id, ingredient_id)` — at most one entry per ingredient per recipe
- `recipe_ingredient.quantity_display: Decimal` — display quantity (use this, not `quantity_normalized`)
- `recipe_ingredient.unit_display: str` — display unit
- `recipe_ingredient.ingredient.canonical_name: str` — item name
- `recipe_ingredient.ingredient.category: str | None` — item category

**Deduplication logic:**
```python
existing_keys = {
    (item.ingredient_id, item.recipe_id)
    for item in shopping_list.items
    if item.archived_at is None
}
# Skip if (ingredient.id, recipe.id) in existing_keys
```

**Recipe access check (from `get_recipe.py:46-56`):**
```python
membership = self.database.find_by(
    RecipeBookUser,
    user_id=user.id,
    recipe_book_id=recipe.recipe_book_id
)
if not membership:
    raise APIException(status_code=403, detail="...", code=ErrorCode.RECIPE_ACCESS_DENIED)
```

**Shopping list access check (from all item endpoints):**
```python
is_owner = shopping_list.owner_id == user.id
membership = self.database.find_by(ShoppingListUser, shopping_list_id=list_id, user_id=user.id)
can_edit = is_owner or (membership and membership.role in ("owner", "editor") and not membership.archived_at)
```

**`database.db.commit()` placement:** Call once after all items are created (not per item) for atomicity. But `database.db.refresh(item)` must be called per item before adding to response (to populate `id`, `created_at`, `updated_at`).

Wait — `refresh()` requires items to already be flushed. Pattern from `generate_from_meal_event.py`:
```python
self.database.create(item)   # calls db.add() + db.flush()
self.database.db.refresh(item)  # now id/timestamps are populated
item_responses.append(...)
```

**Important:** Call `database.db.commit()` AFTER the loop (not inside), and only call `refresh` per item if needed. Actually, `database.create()` likely does `db.add()` + `db.flush()` which populates the item ID. Check the `create()` implementation pattern from existing endpoints.

**`datetime.now(timezone.utc)`** — Always use `from datetime import datetime, timezone` and `datetime.now(timezone.utc)`, never `datetime.utcnow()`.

### Router Broadcast Pattern

Each added item must be broadcast individually as `item_added`. This is intentional — the Flutter `ShoppingListScreen` WebSocket handler only processes `item_added` events (one at a time).

```python
result = PopulateFromRecipe.call(...)
response_data = json.loads(result.body)  # Direct data, no ["data"] wrapper
for item in response_data.get("items", []):
    await broadcast_event_to_list(list_id, "item_added", item, user_id=str(user.id))
return result
```

**Critical:** `json.loads(result.body)` gives the raw data dict directly (see Story 8.1 debug — `Endpoint.call()` wraps in `CustomJSONResponse` with the data value as body, NOT `{"data": {...}}`). So `response_data` will be the `PopulateFromRecipe.Response` dict with `items_added`, `items_skipped`, `items`.

### Flutter: ShoppingCartService `populateFromRecipe`

Simple HTTP POST. The `ApiClient` wraps all responses. Look at `addItem()` at line 70-86 for the pattern:

```dart
Future<ShoppingListItem> addItem(String listId, {...}) async {
  final response = await _apiClient.addShoppingListItem(listId, {...});
  return ShoppingListItem.fromJson(response.data as Map<String, dynamic>);
}
```

For our method, the response data has `items_added`, `items_skipped`, `items`. We just need the counts:
```dart
Future<({int itemsAdded, int itemsSkipped})> populateFromRecipe(
  String listId, String recipeId) async {
  final response = await _apiClient.populateShoppingListFromRecipe(
    listId, {'recipe_id': recipeId});
  final data = response.data as Map<String, dynamic>;
  return (itemsAdded: data['items_added'] as int, itemsSkipped: data['items_skipped'] as int);
}
```

### Flutter: RecipeDetailScreen `_addIngredientsToCart`

The recipe ID is available in the screen as `_recipe?['id']`. The existing `_recipe` map has all recipe data loaded in `_loadRecipe()`.

The `PopupMenuButton` is at line 422 in `recipe_detail_screen.dart`. Current options: `move`, `copy`, `fork`, `archive`. Add `add_to_cart` as the FIRST option (most commonly used action).

**List picker pattern** — use `showModalBottomSheet`:
```dart
final selectedList = await showModalBottomSheet<ShoppingList>(
  context: context,
  builder: (context) => ListView.builder(
    itemCount: lists.length,
    itemBuilder: (context, i) => ListTile(
      leading: const Icon(Icons.shopping_cart_outlined),
      title: Text(lists[i].name.isEmpty ? 'Shopping List' : lists[i].name),
      subtitle: Text('${lists[i].uncheckedCount} items'),
      onTap: () => Navigator.of(context).pop(lists[i]),
    ),
  ),
);
```

**ShoppingCartService import in RecipeDetailScreen:**
```dart
import 'package:palateful/features/shopping_cart/models/shopping_list.dart';
import 'package:palateful/features/shopping_cart/services/shopping_cart_service.dart';
```

### API Client Pattern

`api_client.dart` uses Dio. All shopping list methods are already there (lines 296-350). Add after line 350:
```dart
Future<Response> populateShoppingListFromRecipe(
    String listId, Map<String, dynamic> data) =>
    _dio.post('/v1/shopping-lists/$listId/populate-from-recipe', data: data);
```

### Backend Test Pattern

Use the conftest `MockShoppingList`, `MockShoppingListItem`, `MockShoppingListUser` fixtures. For recipe mocking, you'll need `MockRecipe` and `MockRecipeIngredient` — check if these exist in `conftest.py`. If not, create inline mock objects following the `MockModel` pattern:
```python
class MockRecipeIngredient:
    def __init__(self, ingredient_id, recipe_id, quantity_display=Decimal("1.0"), unit_display="cup", is_optional=False):
        self.ingredient_id = uuid.UUID(ingredient_id)
        self.recipe_id = uuid.UUID(recipe_id)
        self.quantity_display = quantity_display
        self.unit_display = unit_display
        self.is_optional = is_optional
        self.archived_at = None
        self.ingredient = MockIngredient(ingredient_id)

class MockIngredient:
    def __init__(self, ingredient_id):
        self.id = uuid.UUID(ingredient_id)
        self.canonical_name = "Test Ingredient"
        self.category = "Produce"
```

For the broadcast test, patch `broadcast_event_to_list` with `AsyncMock` on `routers.v1.shopping_list_router.broadcast_event_to_list`.

### Project Structure Notes

- New file: `services/api/src/api/v1/shopping_list/populate_from_recipe.py`
- Modified: `services/api/src/api/v1/shopping_list/__init__.py`
- Modified: `services/api/src/routers/v1/shopping_list_router.py`
- Modified: `app/lib/core/services/api_client.dart`
- Modified: `app/lib/features/shopping_cart/services/shopping_cart_service.dart`
- Modified: `app/lib/features/recipes/recipe_detail_screen.dart`
- New: `services/api/tests/test_populate_from_recipe.py`
- New: `app/test/features/recipes/add_to_cart_test.dart`

### References

- Recipe access control: `services/api/src/api/v1/recipe/get_recipe.py:44-56`
- Shopping list access check: `services/api/src/api/v1/shopping_list/delete_item.py:38-53`
- Ingredient iteration pattern: `services/api/src/api/v1/shopping_list/generate_from_meal_event.py:92-137`
- RecipeIngredient model: `libraries/utils/utils/models/recipe_ingredient.py`
- Ingredient model: `libraries/utils/utils/models/ingredient.py`
- ShoppingCartService addItem: `app/lib/features/shopping_cart/services/shopping_cart_service.dart:70-86`
- ApiClient shopping list methods: `app/lib/core/services/api_client.dart:296-350`
- RecipeDetailScreen PopupMenu: `app/lib/features/recipes/recipe_detail_screen.dart:422-479`
- Broadcast pattern (Story 8.1): `services/api/src/routers/v1/shopping_list_router.py`
- `populate_from_calendar.py` deduplication: `services/api/src/api/v1/shopping_list/populate_from_calendar.py:113-145`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- UUID type mismatch in deduplication tests: MockShoppingListItem with `ingredient_id=uuid.UUID(...)` creates UUID objects, but `ingredient.id` from `MockIngredient(id=str(...))` is a string. Fixed by passing string IDs to `MockShoppingListItem` in tests.

### Completion Notes List

- Created `PopulateFromRecipe` endpoint following `generate_from_meal_event.py` pattern; adds recipe ingredients to existing list with deduplication and access control
- Updated `__init__.py` and `shopping_list_router.py` with import and route; broadcasts `item_added` per added item
- Added `populateShoppingListFromRecipe()` to `ApiClient` and `populateFromRecipe()` returning Dart record to `ShoppingCartService`
- Added `_addIngredientsToCart()` to `RecipeDetailScreen` with empty-list snackbar, single-list auto-select, multi-list picker, success/error snackbars; "Add to Cart" is first popup menu item
- 10 backend tests in 5 classes; 7 Flutter widget tests in 4 groups; 305 backend + all Flutter tests pass

### File List

- services/api/src/api/v1/shopping_list/populate_from_recipe.py (new)
- services/api/src/api/v1/shopping_list/__init__.py (modified)
- services/api/src/routers/v1/shopping_list_router.py (modified)
- app/lib/core/services/api_client.dart (modified)
- app/lib/features/shopping_cart/services/shopping_cart_service.dart (modified)
- app/lib/features/recipes/recipe_detail_screen.dart (modified)
- services/api/tests/test_populate_from_recipe.py (new)
- app/test/features/recipes/add_to_cart_test.dart (new)
- _bmad-output/implementation-artifacts/8-2-add-recipe-ingredients-to-shopping-list.md (modified)
- _bmad-output/implementation-artifacts/sprint-status.yaml (modified)
