# Story 9.3: Add Planned Meal Ingredients to Shopping List

Status: review

## Story

As a user,
I want to add ingredients from a planned meal to the shopping list,
So that planning and shopping are connected without manual effort.

## Acceptance Criteria

1. **"Add ingredients" option on meal event** — Long-pressing a calendar meal tile shows an "Add ingredients to cart" option (only shown when the event has a linked recipe).
2. **List selection** — If the user has one shopping list, ingredients are added automatically. If multiple lists exist, a picker sheet lets them choose. If no lists exist, a snackbar prompts them to create one.
3. **Adds ingredients via existing endpoint** — Calls `POST /v1/shopping-lists/{list_id}/populate-from-recipe` with the event's `recipe_id`. Duplicate handling (skip if same ingredient+recipe already on list) and real-time sync are handled by the backend (same behaviour as Story 8.2).
4. **Toast confirms result** — On success, a snackbar shows "Added N ingredient(s) to [List Name]". On failure, shows "Failed to add ingredients".
5. **No recipe = option hidden** — The "Add ingredients to cart" option does not appear when the meal event has no linked recipe (`event.recipe == null`).

## Tasks / Subtasks

- [x] Task 1: Add "Add ingredients to cart" option to `CalendarScreen._showEventOptions` (AC: 1, 5)
  - [x] Add a third `ListTile` to the `_showEventOptions` bottom sheet with `Icons.add_shopping_cart_outlined` icon and "Add to shopping list" title
  - [x] Only show the tile when `event.recipe != null`
  - [x] Dismiss the bottom sheet before starting the async flow

- [x] Task 2: Implement list selection and `populateFromRecipe` call (AC: 2, 3, 4)
  - [x] Add `final _cartService = getIt<ShoppingCartService>();` field to `_CalendarScreenState`
  - [x] Add import for `ShoppingCartService` in `calendar_screen.dart`
  - [x] Implement `_addIngredientsFromEvent(MealEvent event)`:
    - Fetch lists via `_cartService.getShoppingLists()`
    - If 0 lists → show snackbar "No shopping lists — tap + to create one" and return
    - If 1 list → call `_cartService.populateFromRecipe(lists[0].id, event.recipe!.id)`
    - If multiple → show list picker sheet; on selection call `populateFromRecipe`
    - On success → show snackbar "Added N ingredient(s) to [List Name]" (singular/plural)
    - On error → show snackbar "Failed to add ingredients"

- [x] Task 3: Flutter widget tests (AC: 1, 4, 5)
  - [x] Create `app/test/features/calendar/add_ingredients_from_calendar_test.dart`
  - [x] Test: long-press on event with recipe shows "Add to shopping list" option
  - [x] Test: long-press on event WITHOUT recipe does NOT show "Add to shopping list"
  - [x] Test: tapping "Add to shopping list" calls `populateFromRecipe` with correct list ID and recipe ID
  - [x] Test: success snackbar shows "Added N ingredient(s) to [List Name]"

## Dev Notes

### No Backend Changes Needed

The backend endpoint `POST /v1/shopping-lists/{list_id}/populate-from-recipe` was fully implemented in Story 8.2:
- Deduplication by `(ingredient_id, recipe_id)` — skips already-added ingredients
- Access control — 403 if user can't edit the list
- Real-time sync — broadcasts each added item as `item_added` via WebSocket
- Returns `{ items_added: int, items_skipped: int, items: [...] }`

### Existing Flutter Infrastructure (already in place)

**`ShoppingCartService`** (`app/lib/features/shopping_cart/services/shopping_cart_service.dart`):
```dart
// Already exists:
Future<List<ShoppingList>> getShoppingLists() async { ... }
Future<({int itemsAdded, int itemsSkipped})> populateFromRecipe(String listId, String recipeId) async {
  final response = await _apiClient.populateShoppingListFromRecipe(listId, {'recipe_id': recipeId});
  final data = response.data as Map<String, dynamic>;
  return (itemsAdded: data['items_added'] as int, itemsSkipped: data['items_skipped'] as int);
}
```

**`ApiClient`** (`app/lib/core/services/api_client.dart`):
```dart
// Already exists:
Future<Response> populateShoppingListFromRecipe(String listId, Map<String, dynamic> data) =>
    _dio.post('/v1/shopping-lists/$listId/populate-from-recipe', data: data);
```

**DI** (`app/lib/core/di/injection.dart`):
```dart
// Already registered:
getIt.registerLazySingleton<ShoppingCartService>(() => ShoppingCartService());
```

### Current `_showEventOptions` Structure

```dart
// app/lib/features/calendar/calendar_screen.dart:103–148
void _showEventOptions(MealEvent event) {
  showModalBottomSheet(
    context: context,
    builder: (ctx) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            leading: const Icon(Icons.edit_calendar_outlined),
            title: const Text('Reschedule'),
            onTap: () async { ... },
          ),
          ListTile(
            leading: Icon(Icons.delete_outline, color: Theme.of(context).colorScheme.error),
            title: Text('Remove', style: TextStyle(color: Theme.of(context).colorScheme.error)),
            onTap: () { ... },
          ),
        ],
      ),
    ),
  );
}
```

**Add the third tile** (only when recipe != null):
```dart
if (event.recipe != null)
  ListTile(
    leading: const Icon(Icons.add_shopping_cart_outlined),
    title: const Text('Add to shopping list'),
    onTap: () {
      Navigator.pop(ctx);
      _addIngredientsFromEvent(event);
    },
  ),
```

### `_addIngredientsFromEvent` Implementation

```dart
Future<void> _addIngredientsFromEvent(MealEvent event) async {
  List<ShoppingList> lists;
  try {
    lists = await _cartService.getShoppingLists();
  } catch (_) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to load shopping lists')),
      );
    }
    return;
  }

  if (lists.isEmpty) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No shopping lists — tap + to create one')),
      );
    }
    return;
  }

  final ShoppingList targetList;
  if (lists.length == 1) {
    targetList = lists.first;
  } else {
    // Show picker
    final selected = await showModalBottomSheet<ShoppingList>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('Choose a shopping list',
                  style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16)),
            ),
            ...lists.map((list) => ListTile(
              title: Text(list.name),
              subtitle: Text('${list.items.length} item(s)'),
              onTap: () => Navigator.pop(ctx, list),
            )),
          ],
        ),
      ),
    );
    if (selected == null) return; // cancelled
    targetList = selected;
  }

  try {
    final result = await _cartService.populateFromRecipe(targetList.id, event.recipe!.id);
    if (mounted) {
      final n = result.itemsAdded;
      final label = n == 1 ? '1 ingredient' : '$n ingredients';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Added $label to ${targetList.name}')),
      );
    }
  } catch (_) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to add ingredients')),
      );
    }
  }
}
```

### `ShoppingList` Model

Check the existing `ShoppingList` model in `app/lib/features/shopping_cart/` — it has `id`, `name`, `items`, etc. Use the model's actual field names (may be `items` or `itemCount`).

### Test Pattern

Extend the existing `_FakeMealCalendarService` pattern from 9.1 tests. For `ShoppingCartService`, create a `_FakeShoppingCartService`:

```dart
class _FakeShoppingCartService extends ShoppingCartService {
  final List<ShoppingList> lists;
  String? lastPopulateListId;
  String? lastPopulateRecipeId;
  int itemsAddedResult;

  _FakeShoppingCartService({
    this.lists = const [],
    this.itemsAddedResult = 3,
  });

  @override
  Future<List<ShoppingList>> getShoppingLists() async => lists;

  @override
  Future<({int itemsAdded, int itemsSkipped})> populateFromRecipe(
      String listId, String recipeId) async {
    lastPopulateListId = listId;
    lastPopulateRecipeId = recipeId;
    return (itemsAdded: itemsAddedResult, itemsSkipped: 0);
  }
}
```

Note: `ShoppingCartService` is NOT an interface — it's a concrete class. You'll need to either:
- Subclass it (override the methods needed)
- Or check if it has constructor params that allow injection

`ShoppingCartService` constructor signature: check the file — it uses `getIt<ApiClient>()` internally. Create fake as subclass overriding only `getShoppingLists` and `populateFromRecipe`.

For widget test that needs to trigger the long-press options sheet:
```dart
await tester.longPress(find.text('Pasta Night')); // long-press on event title
await tester.pumpAndSettle();
// Then check for the option
expect(find.text('Add to shopping list'), findsOneWidget);
```

### Project Structure Notes

- Modified files:
  - `app/lib/features/calendar/calendar_screen.dart` — add third option + `_addIngredientsFromEvent` method + `ShoppingCartService` field
- New files:
  - `app/test/features/calendar/add_ingredients_from_calendar_test.dart`

### References

- Epic 9 story 9.3: `_bmad-output/planning-artifacts/epics.md`
- Story 8.2 (existing populate-from-recipe flow): `_bmad-output/implementation-artifacts/8-2-add-recipe-ingredients-to-shopping-list.md`
- Backend endpoint: `services/api/src/api/v1/shopping_list/populate_from_recipe.py`
- `ShoppingCartService`: `app/lib/features/shopping_cart/services/shopping_cart_service.dart`
- `ShoppingList` model: `app/lib/features/shopping_cart/models/`
- `CalendarScreen._showEventOptions`: `app/lib/features/calendar/calendar_screen.dart:103`
- DI injection: `app/lib/core/di/injection.dart`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- ✅ Task 1: Added "Add to shopping list" `ListTile` to `_showEventOptions` bottom sheet; guarded by `event.recipe != null`; dismisses sheet before async flow
- ✅ Task 2: Added `_cartService` field, `ShoppingCartService` + `ShoppingList` imports, and full `_addIngredientsFromEvent` method with 0/1/multi list logic and success/error snackbars
- ✅ Task 3: 5 widget tests in `add_ingredients_from_calendar_test.dart` — option visibility (with/without recipe), correct IDs passed, plural/singular snackbar messages; also fixed `calendar_screen_test.dart` to register `ShoppingCartService` stub (needed after 9.3 added `_cartService` field); all Flutter tests pass

### File List

- `app/lib/features/calendar/calendar_screen.dart` — added `ShoppingCartService`/`ShoppingList` imports, `_cartService` field, third `ListTile` in `_showEventOptions`, `_addIngredientsFromEvent` method
- `app/test/features/calendar/add_ingredients_from_calendar_test.dart` — new file with 5 widget tests
- `app/test/features/calendar/calendar_screen_test.dart` — added `ApiClient`, `ShoppingCartService`, `ShoppingList` stubs + registration to fix failures caused by new `_cartService` field
