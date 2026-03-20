# Story 9.4: Aggregate Shopping List from Date Range

Status: review

## Story

As a user,
I want to generate a combined shopping list from all planned meals across a date range,
So that I can do one grocery run for the whole week.

## Acceptance Criteria

1. **"Generate list for this week" action** — A button/action in the `CalendarScreen` lets the user add all planned meal ingredients for the currently displayed week to a shopping list in one tap.
2. **List selection** — If the user has one shopping list, ingredients are added automatically. If multiple lists exist, a picker sheet lets them choose (same pattern as Story 9.3). If no lists exist, a snackbar prompts them to create one.
3. **Date-range aggregation via existing endpoint** — Calls `POST /v1/shopping-lists/{list_id}/populate-from-calendar` with `start_date` and `end_date` derived from the current week (`_weekStart` and `_weekEnd` in `CalendarScreen`). Backend already handles deduplication and source attribution.
4. **Toast confirms result** — On success, a snackbar shows "Added N ingredient(s) from M meal(s) to [List Name]" (singular/plural for both). On failure, shows "Failed to generate shopping list".
5. **Real-time sync** — The backend router must broadcast each added item to connected WebSocket clients (same `broadcast_event_to_list` pattern as `populate-from-recipe`). This satisfies the "syncs to my partner in real-time" AC.
6. **Empty week** — If the current week has no planned meals (or none with recipes), shows snackbar "No planned meals with recipes this week".
7. **Backend tests** — `test_populate_from_calendar.py` covers success, skip-on-duplicate, empty-events, and access-denied scenarios.

## Tasks / Subtasks

- [x] Task 1: Fix backend router to broadcast WebSocket events (AC: 5)
  - [x] In `services/api/src/routers/v1/shopping_list_router.py`, update the `populate_from_calendar` route handler to broadcast each added item with `broadcast_event_to_list` (same pattern as `populate_from_recipe` at lines 287-297)
  - [x] Ensure `populate_from_calendar` route is `async` (it already is, just needs the broadcast loop)

- [x] Task 2: Add backend tests for `PopulateFromCalendar` (AC: 7)
  - [x] Create `services/api/tests/test_populate_from_calendar.py`
  - [x] Test: success — meal event with recipe adds ingredients, returns correct `items_added` count
  - [x] Test: skip duplicate — ingredient already in list for that meal event is skipped
  - [x] Test: no meal events in range — returns `items_added=0, meal_events_included=0`
  - [x] Test: access denied — user without edit permission gets 403

- [x] Task 3: Add `populateShoppingListFromCalendar` to `ApiClient` (AC: 3)
  - [x] In `app/lib/core/services/api_client.dart`, add method after `populateShoppingListFromRecipe`:

- [x] Task 4: Add `populateFromCalendarRange` to `ShoppingCartService` (AC: 3)
  - [x] In `app/lib/features/shopping_cart/services/shopping_cart_service.dart`, add method after `populateFromRecipe`

- [x] Task 5: Add "Generate list for this week" button to `CalendarScreen` (AC: 1, 2, 4, 6)
  - [x] Add action icon button to the `_buildAppBar` (right side of AppBar) with `Icons.add_shopping_cart_outlined`
  - [x] On tap, call `_generateWeeklyShoppingList()`
  - [x] Implement `_generateWeeklyShoppingList()` method

- [x] Task 6: Flutter widget tests (AC: 1, 4, 6)
  - [x] Create `app/test/features/calendar/generate_weekly_list_test.dart`
  - [x] Test: "Generate" button is visible in CalendarScreen app bar
  - [x] Test: tapping button with single list calls `populateFromCalendarRange` with correct start/end dates
  - [x] Test: success snackbar shows correct plural count
  - [x] Test: success snackbar uses singular for 1 ingredient from 1 meal
  - [x] Test: snackbar shows "No planned meals with recipes this week" when 0 meals included
  - [x] Test: snackbar shows error message when `populateFromCalendarRange` throws

## Dev Notes

### Backend: The Endpoint Already Exists

`POST /v1/shopping-lists/{list_id}/populate-from-calendar` is fully implemented:

**File:** `services/api/src/api/v1/shopping_list/populate_from_calendar.py`

```python
class PopulateFromCalendar(Endpoint):
    class Params(BaseModel):
        start_date: date | None = None
        end_date: date | None = None
        check_pantry: bool = True
        include_meal_event_ids: list[str] | None = None

    class Response(BaseModel):
        items_added: int
        items_skipped: int
        meal_events_included: int
        meal_events: list[dict]
        items: list[dict]
```

Router registration already at `services/api/src/routers/v1/shopping_list_router.py:300`.

**The only backend change needed:** The route handler does NOT yet broadcast WebSocket events. Look at `populate-from-recipe` handler (lines 287-297 in router) — it does:
```python
for item in response_data.get("items", []):
    await broadcast_event_to_list(list_id, "item_added", item, user_id=str(user.id))
```
Add the same loop to `populate_from_calendar` route handler.

### Backend: `populate_from_calendar` Route Handler (current)

```python
@shopping_list_router.post("/shopping-lists/{list_id}/populate-from-calendar")
async def populate_from_calendar(
    list_id: str,
    params: PopulateFromCalendar.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    return PopulateFromCalendar.call(
        list_id=list_id, params=params, user=user, database=database,
    )
```

**Fixed version** (add broadcast loop):
```python
@shopping_list_router.post("/shopping-lists/{list_id}/populate-from-calendar")
async def populate_from_calendar(
    list_id: str,
    params: PopulateFromCalendar.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    result = PopulateFromCalendar.call(
        list_id=list_id, params=params, user=user, database=database,
    )
    response_data = result.body if hasattr(result, 'body') else {}
    if isinstance(response_data, bytes):
        import json
        response_data = json.loads(response_data)
    for item in response_data.get("items", []):
        await broadcast_event_to_list(list_id, "item_added", item, user_id=str(user.id))
    return result
```

> **Note:** Check the exact pattern used for `populate_from_recipe` broadcast (lines 280-297 in router) — it extracts `response_data` from the result. Follow the exact same approach.

### Backend Test Pattern

Follow `test_populate_from_recipe.py` pattern. Key mocks needed:
- `MockShoppingList` from `conftest.py`
- `MockMealEvent` from `conftest.py` (has `scheduled_at`, `status`, `recipe`, `owner_id`)
- `MockRecipe` with `ingredients` list → `MockRecipeIngredient` → `MockIngredient`
- Set `mock_db.query_filter_results` for `MealEvent` query

Backend endpoint URL: `POST /v1/shopping-lists/{list_id}/populate-from-calendar`
Request body: `{"start_date": "2026-03-17", "end_date": "2026-03-23"}`

### Flutter: `ApiClient` — Existing Pattern to Follow

```dart
// Existing (line 353-357):
Future<Response> populateShoppingListFromRecipe(
    String listId, Map<String, dynamic> data) {
  return _dio.post('/v1/shopping-lists/$listId/populate-from-recipe', data: data);
}

// New method — add right after:
Future<Response> populateShoppingListFromCalendar(
    String listId, Map<String, dynamic> data) {
  return _dio.post('/v1/shopping-lists/$listId/populate-from-calendar', data: data);
}
```

### Flutter: `ShoppingCartService` — Date Formatting

The backend expects ISO date strings (`"2026-03-17"`). Use this helper or inline formatting:
```dart
String _isoDate(DateTime d) =>
    '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
```

`populateFromCalendarRange` returns a named record — note the **3-field** tuple (unlike 2-field `populateFromRecipe`).

### Flutter: `CalendarScreen` — Where to Add the Button

Current `_buildAppBar` returns an `AppBar` with `title: _buildWeekNavigator()` centered. Add an `actions` parameter with the generate button:

```dart
PreferredSizeWidget _buildAppBar() {
  return AppBar(
    backgroundColor: AppColors.cream,
    elevation: 0,
    title: _buildWeekNavigator(),
    actions: [
      IconButton(
        icon: const Icon(Icons.add_shopping_cart_outlined),
        color: AppColors.textPrimary,
        tooltip: 'Add week to shopping list',
        onPressed: _generateWeeklyShoppingList,
      ),
    ],
  );
}
```

### Flutter: `_generateWeeklyShoppingList` Method

Full implementation:
```dart
Future<void> _generateWeeklyShoppingList() async {
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
    if (!mounted) return;
    final selected = await showModalBottomSheet<ShoppingList>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                'Choose a shopping list',
                style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
              ),
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
    if (selected == null) return;
    targetList = selected;
  }

  try {
    final result = await _cartService.populateFromCalendarRange(
        targetList.id, _weekStart, _weekEnd);
    if (mounted) {
      if (result.mealEventsIncluded == 0) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No planned meals with recipes this week')),
        );
        return;
      }
      final n = result.itemsAdded;
      final m = result.mealEventsIncluded;
      final itemLabel = n == 1 ? '1 ingredient' : '$n ingredients';
      final mealLabel = m == 1 ? '1 meal' : '$m meals';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Added $itemLabel from $mealLabel to ${targetList.name}')),
      );
    }
  } catch (_) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to generate shopping list')),
      );
    }
  }
}
```

### Flutter: Test Setup Pattern

Follow `add_ingredients_from_calendar_test.dart` exactly:
- `setUpAll` loads dotenv
- `setUp` registers `_FakeApiClient` in GetIt
- `tearDown` unregisters all
- `_FakeShoppingCartService` extends `ShoppingCartService` and overrides `getShoppingLists` and `populateFromCalendarRange`

The new `_FakeShoppingCartService` needs to override `populateFromCalendarRange` (3-field record) instead of `populateFromRecipe`. Capture `lastStart` and `lastEnd` to assert correct dates were passed.

Test for the add button:
```dart
await tester.pumpWidget(const MaterialApp(home: CalendarScreen()));
await tester.pump();
// The button should be in the AppBar actions
expect(find.byIcon(Icons.add_shopping_cart_outlined), findsOneWidget);
await tester.tap(find.byIcon(Icons.add_shopping_cart_outlined));
await tester.pumpAndSettle();
```

### Snackbar Message Format

| Scenario | Message |
|---|---|
| 1 ingredient from 1 meal | `Added 1 ingredient from 1 meal to Groceries` |
| 4 ingredients from 2 meals | `Added 4 ingredients from 2 meals to Groceries` |
| 0 meal events with recipes | `No planned meals with recipes this week` |
| populateFromCalendarRange throws | `Failed to generate shopping list` |
| getShoppingLists throws | `Failed to load shopping lists` |
| No shopping lists | `No shopping lists — tap + to create one` |

### Project Structure Notes

- Modified files:
  - `services/api/src/routers/v1/shopping_list_router.py` — add broadcast loop to `populate_from_calendar` route
  - `app/lib/core/services/api_client.dart` — add `populateShoppingListFromCalendar`
  - `app/lib/features/shopping_cart/services/shopping_cart_service.dart` — add `populateFromCalendarRange`
  - `app/lib/features/calendar/calendar_screen.dart` — add `actions` to AppBar + `_generateWeeklyShoppingList` method
- New files:
  - `services/api/tests/test_populate_from_calendar.py`
  - `app/test/features/calendar/generate_weekly_list_test.dart`

### References

- Epic 9.4 story: `_bmad-output/planning-artifacts/epics.md` (line 1051)
- Backend endpoint (complete): `services/api/src/api/v1/shopping_list/populate_from_calendar.py`
- Router (needs broadcast fix): `services/api/src/routers/v1/shopping_list_router.py:300-313`
- Broadcast pattern reference: `services/api/src/routers/v1/shopping_list_router.py:280-297` (populate_from_recipe)
- ApiClient: `app/lib/core/services/api_client.dart:353-357`
- ShoppingCartService: `app/lib/features/shopping_cart/services/shopping_cart_service.dart:131-142`
- CalendarScreen: `app/lib/features/calendar/calendar_screen.dart`
- Story 9.3 test patterns: `app/test/features/calendar/add_ingredients_from_calendar_test.dart`
- Backend test pattern: `services/api/tests/test_populate_from_recipe.py`
- MockMealEvent: `services/api/tests/conftest.py:218`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Fixed 3 pre-existing field name bugs in `populate_from_calendar.py`: `ingredient.name` → `canonical_name`, `recipe_ingredient.quantity` → `quantity_display`, `recipe_ingredient.unit` → `unit_display`
- Backend tests require `MockQuery([event])` pattern (not MagicMock chaining) and `MockRecipe.steps = []` to satisfy `calculate_item_due_date`
- `ShoppingListUser` imports from `utils.models.shopping_list_user`, not `utils.models.shopping_list`

### File List

- `services/api/src/routers/v1/shopping_list_router.py` — added broadcast loop to `populate_from_calendar` route
- `services/api/src/api/v1/shopping_list/populate_from_calendar.py` — fixed field names (`canonical_name`, `quantity_display`, `unit_display`)
- `services/api/tests/test_populate_from_calendar.py` — new: 6 backend tests
- `app/lib/core/services/api_client.dart` — added `populateShoppingListFromCalendar`
- `app/lib/features/shopping_cart/services/shopping_cart_service.dart` — added `populateFromCalendarRange`
- `app/lib/features/calendar/calendar_screen.dart` — added AppBar `actions` button + `_generateWeeklyShoppingList` method
- `app/test/features/calendar/generate_weekly_list_test.dart` — new: 7 Flutter widget tests
