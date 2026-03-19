# Story 8.1: Shared Real-Time Shopping List

Status: done

## Story

As a user,
I want to manage a shared shopping list with my household where items sync in real-time,
So that we always see the same list without texting "did you get the lemons?"

## Acceptance Criteria

1. **Given** I navigate to the Cart tab, **When** the screen loads, **Then** I see my shopping lists (owned and shared), or an empty state with a "Create list" CTA if none exist.

2. **Given** I tap "Create list", **When** I enter a name and confirm, **Then** a new shopping list is created and I am navigated into it (the `ShoppingListScreen`).

3. **Given** a shopping list exists, **When** I tap it in the Cart tab, **Then** I navigate to the `ShoppingListScreen` for that list.

4. **Given** I am viewing a shopping list and I add an item, **When** my household partner is also viewing the same list, **Then** the item appears on their screen within 1 second (real-time WebSocket broadcast).

5. **Given** my partner checks off an item, **When** the item is updated on the server, **Then** the checked state appears on my screen within 1 second (real-time WebSocket broadcast).

6. **Given** my partner deletes an item, **When** the item is removed on the server, **Then** the item disappears from my screen within 1 second (real-time WebSocket broadcast).

7. **Given** I tap "Join list" and enter a share code, **When** the code is valid, **Then** I join the list and am navigated to its `ShoppingListScreen`.

8. **Given** items display in the list, **Then** unchecked items and checked items are grouped, and I can manually add items by typing.

## Tasks / Subtasks

- [x] Task 1: Backend — Add `updated_at` to `ListShoppingLists` response (AC: 1, 3)
  - [x] 1.1 In `services/api/src/api/v1/shopping_list/list_shopping_lists.py`, add `updated_at: datetime` to `ListShoppingLists.ShoppingListItem` Pydantic model
  - [x] 1.2 In `ListShoppingLists.execute()`, populate `updated_at=sl.updated_at` in each `ShoppingListItem(...)` instantiation

- [x] Task 2: Backend — Wire WebSocket broadcasts in shopping list router (AC: 4, 5, 6)
  - [x] 2.1 In `services/api/src/routers/v1/shopping_list_router.py`, import `broadcast_event_to_list` from `api.v1.shopping_list`
  - [x] 2.2 In `add_shopping_list_item` router endpoint, after `result = AddShoppingListItem.call(...)`, extract item data from result and call `await broadcast_event_to_list(list_id, "item_added", item_data, user_id=str(user.id))`
  - [x] 2.3 In `update_shopping_list_item` router endpoint, after `result = UpdateShoppingListItem.call(...)`, call `await broadcast_event_to_list(list_id, "item_updated", item_data, user_id=str(user.id))` (use `"item_checked"` when `params.is_checked is not None`)
  - [x] 2.4 In `delete_shopping_list_item` router endpoint, after `result = DeleteShoppingListItem.call(...)`, call `await broadcast_event_to_list(list_id, "item_removed", {"item_id": item_id}, user_id=str(user.id))`

- [x] Task 3: Flutter — Replace CartScreen placeholder with shopping list index (AC: 1, 2, 3, 7, 8)
  - [x] 3.1 Convert `app/lib/features/cart/cart_screen.dart` from `StatelessWidget` placeholder to `StatefulWidget`
  - [x] 3.2 Add state: `List<ShoppingList> _lists`, `bool _isLoading`, `String? _error`; use `ShoppingCartService` via `getIt<ShoppingCartService>()`
  - [x] 3.3 In `initState`, call `_loadLists()` which calls `_service.getShoppingLists()` and stores results in `_lists`
  - [x] 3.4 Build list view: each item shows list name, item count, shared indicator; tap navigates to `/shopping-lists/${list.id}`
  - [x] 3.5 Add FAB or prominent button for "Create list" — shows `AlertDialog` with a `TextField` for name, calls `_service.createShoppingList(name)`, then navigates to the new list
  - [x] 3.6 Add "Join list" option in AppBar menu or secondary button — shows dialog with a `TextField` for share code, calls `_service.joinList(shareCode)`, navigates to joined list
  - [x] 3.7 Show `EmptyStateWidget` when `_lists` is empty with title "No shopping lists yet", subtitle "Tap + to create your first list"

- [x] Task 4: Flutter — Add shopping list detail route (AC: 3)
  - [x] 4.1 In `app/lib/core/router/app_router.dart`, under the Cart branch (after `path: '/cart'`), add a nested `GoRoute` for `path: '/shopping-lists/:id'` → `ShoppingListScreen(listId: state.pathParameters['id']!)`
  - [x] 4.2 Import `ShoppingListScreen` in `app_router.dart`

- [x] Task 5: Backend — Tests (AC: 4, 5, 6)
  - [x] 5.1 Create `services/api/tests/test_shopping_list_router_broadcasts.py` with tests using `AsyncMock` to verify that `add_shopping_list_item`, `update_shopping_list_item`, and `delete_shopping_list_item` router calls trigger `broadcast_event_to_list` with the correct event types
  - [x] 5.2 Test `ListShoppingLists` response includes `updated_at`
  - [x] 5.3 All 295 backend tests pass (was 288 before this story)

- [x] Task 6: Flutter — Tests (AC: 1, 2, 3)
  - [x] 6.1 Create `app/test/features/cart/cart_screen_test.dart` with 9 widget tests covering: list name display, fallback name, item count, "All done!", "Empty", shared icon, onTap callback
  - [x] 6.2 All Flutter tests continue to pass (exit code 0)

## Dev Notes

### Critical Architecture: WebSocket Broadcast Pattern

The WebSocket infrastructure for shopping lists is **fully built**. The missing piece is the **router-level broadcast** after item mutations. Pattern to follow (from `recipe_router.py`):

```python
# In shopping_list_router.py (async def endpoint)
result = AddShoppingListItem.call(
    list_id=list_id,
    params=params,
    user=user,
    database=database,
)
# Fire broadcast to all connected clients
await broadcast_event_to_list(
    list_id, "item_added",
    {"item_id": "...", "name": params.name, ...},
    user_id=str(user.id),
)
return result
```

**Import**: `from api.v1.shopping_list import broadcast_event_to_list` (already imported in `__init__.py` via websocket.py)

**Key point**: `Endpoint.call()` raises `HTTPException` on errors — the broadcast only runs if `call()` returns successfully. No try/except needed.

**broadcast_event_to_list signature**:
```python
async def broadcast_event_to_list(
    shopping_list_id: str | uuid.UUID,
    event_type: str,       # "item_added" | "item_updated" | "item_checked" | "item_removed"
    event_data: dict[str, Any],
    user_id: str | uuid.UUID | None = None,
    sequence: int | None = None,
)
```

### Flutter: Extracting Broadcast Data from Router Result

`Endpoint.call()` returns a `CustomJSONResponse`. To extract the item data for the broadcast, use a dict with minimal fields rather than parsing the result. For `item_added`:
```python
await broadcast_event_to_list(
    list_id, "item_added",
    {
        "id": str(item_id_from_result),  # or re-fetch from DB
        "name": params.name,
        ...
    },
    user_id=str(user.id),
)
```

**Simpler approach**: Re-fetch the item from DB after `call()`. But the simplest correct approach: the `AddShoppingListItem` endpoint creates an item and returns its ID. Since `Endpoint.call()` returns `CustomJSONResponse`, parse `result.body` or just pass `params.name` and the list_id. For the `item_removed` event, just pass `{"item_id": item_id}`.

**Concrete patterns for each event type:**

For `add_shopping_list_item`, item data to broadcast:
```python
# The response data contains the created item — extract from result
import json
response_data = json.loads(result.body)["data"]
await broadcast_event_to_list(list_id, "item_added", response_data, user_id=str(user.id))
```

For `update_shopping_list_item`, determine event type from params:
```python
response_data = json.loads(result.body)["data"]
event_type = "item_checked" if params.is_checked is not None else "item_updated"
await broadcast_event_to_list(list_id, event_type, response_data, user_id=str(user.id))
```

For `delete_shopping_list_item`:
```python
await broadcast_event_to_list(list_id, "item_removed", {"item_id": item_id}, user_id=str(user.id))
```

### `CustomJSONResponse.body` Contains the Full Response

`Endpoint.call()` returns `CustomJSONResponse` which is a Starlette `Response`. Its `.body` attribute is bytes. Parse with `json.loads(result.body)["data"]` to get the response data dict.

**Reference**: `libraries/utils/utils/api/endpoint.py` — `CustomJSONResponse` extends `JSONResponse`.

### `ListShoppingLists` Missing `updated_at`

`ShoppingList.fromJson` (Flutter) requires `updated_at: DateTime.parse(json['updated_at'] as String)` — if null it throws. The `ListShoppingLists.ShoppingListItem` Pydantic response model currently lacks `updated_at`. Add it (Task 1).

**Reference**: `services/api/src/api/v1/shopping_list/list_shopping_lists.py:119-132`

### Flutter CartScreen Pattern

Follow `RecipeBooksScreen` as the closest pattern for a "list index" screen:
- `StatefulWidget` with `_isLoading`, `_error`, `_lists` state
- `initState` → `_loadLists()` async
- `RefreshIndicator` wrapping `ListView.builder`
- FAB for primary create action
- `EmptyStateWidget` when empty

**Reference for empty state**: `app/lib/shared/widgets/empty_state.dart`
**Reference for list card pattern**: `app/lib/features/recipe_books/recipe_books_screen.dart`

### Flutter Route Addition

The Cart tab branch in `app_router.dart` currently only has `/cart`. Shopping list detail needs to be routable:

```dart
// In StatefulShellBranch for cart:
StatefulShellBranch(
  navigatorKey: _cartNavigatorKey,
  routes: [
    GoRoute(
      path: '/cart',
      builder: (context, state) => const CartScreen(),
    ),
    GoRoute(
      path: '/shopping-lists/:id',
      builder: (context, state) {
        final id = state.pathParameters['id']!;
        return ShoppingListScreen(listId: id);
      },
    ),
  ],
),
```

**Reference**: `app/lib/core/router/app_router.dart:323-332` (current cart branch)
**Import needed**: `../../features/shopping_cart/screens/shopping_list_screen.dart`

### Real-Time Sync Flow

1. User A adds item → `POST /shopping-lists/{id}/items` → `AddShoppingListItem.call()` creates item → router calls `broadcast_event_to_list("item_added", item_data)` → `ConnectionManager.broadcast_to_list()` sends JSON to all connected WebSockets
2. User B's Flutter app receives `{"type": "item_added", "data": {...}}` → `_itemAddedController.add(item)` → `ShoppingListScreen._handleItemAdded()` → `setState` → UI updates

Both users must be connected via `ShoppingCartService.connectWebSocket(listId)` (called automatically when `ShoppingListScreen` initializes).

### AppSync vs WebSocket Clarification

The epic mentions "AppSync subscriptions" but the codebase uses **FastAPI native WebSockets** (pattern established in Story 7.4). Do NOT use AppSync. The existing `shopping_list_router.py` already has:
```python
@shopping_list_router.websocket("/ws/shopping-lists/{list_id}")
async def shopping_list_websocket(...)
```

### Existing Shopping List Infrastructure (Do NOT Recreate)

These are **fully built** — use them as-is:
- `services/api/src/api/v1/shopping_list/websocket.py` — `ConnectionManager`, `shopping_list_websocket_handler`, `broadcast_event_to_list`
- `app/lib/features/shopping_cart/services/shopping_cart_service.dart` — API + WebSocket service
- `app/lib/features/shopping_cart/screens/shopping_list_screen.dart` — Full shopping list screen
- `app/lib/features/shopping_cart/models/shopping_list.dart` — `ShoppingList`, `ShoppingListMember`, `OnlineUser`
- `app/lib/features/shopping_cart/models/shopping_list_item.dart` — `ShoppingListItem`, `UrgencyLevel`
- All 22 backend endpoint files in `services/api/src/api/v1/shopping_list/`

### `__init__.py` for Shopping List Module

Check `services/api/src/api/v1/shopping_list/__init__.py` to confirm `broadcast_event_to_list` is exported. It should be since it's used by the websocket route in the router.

### Test Pattern for Router Broadcast

Use `unittest.mock.patch` on `broadcast_event_to_list` with `AsyncMock`:
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_add_item_broadcasts():
    with patch("routers.v1.shopping_list_router.broadcast_event_to_list", new_callable=AsyncMock) as mock_broadcast:
        # Call router handler directly with mocked deps
        ...
        mock_broadcast.assert_called_once()
        assert mock_broadcast.call_args[0][1] == "item_added"
```

Or test through the FastAPI test client using `httpx` async client (pattern from existing tests).

### Project Structure Notes

- Modified: `services/api/src/api/v1/shopping_list/list_shopping_lists.py` (add `updated_at` to response)
- Modified: `services/api/src/routers/v1/shopping_list_router.py` (broadcast in 3 router endpoints)
- Modified: `app/lib/features/cart/cart_screen.dart` (replace placeholder with full implementation)
- Modified: `app/lib/core/router/app_router.dart` (add `/shopping-lists/:id` route)
- New: `services/api/tests/test_shopping_list_router_broadcasts.py`
- New: `app/test/features/cart/cart_screen_test.dart`
- New: `app/test/features/cart/` directory

### References

- WebSocket broadcast function: `services/api/src/api/v1/shopping_list/websocket.py:245-269`
- Shopping list router (all 35 endpoints): `services/api/src/routers/v1/shopping_list_router.py`
- `ListShoppingLists` endpoint: `services/api/src/api/v1/shopping_list/list_shopping_lists.py`
- `AddShoppingListItem` endpoint: `services/api/src/api/v1/shopping_list/add_item.py`
- `UpdateShoppingListItem` endpoint: `services/api/src/api/v1/shopping_list/update_item.py`
- `DeleteShoppingListItem` endpoint: `services/api/src/api/v1/shopping_list/delete_item.py`
- `CartScreen` placeholder: `app/lib/features/cart/cart_screen.dart`
- Cart tab route: `app/lib/core/router/app_router.dart:323-332`
- `ShoppingListScreen` (full screen, already built): `app/lib/features/shopping_cart/screens/shopping_list_screen.dart`
- `ShoppingCartService` (already built): `app/lib/features/shopping_cart/services/shopping_cart_service.dart`
- `ShoppingList.fromJson`: `app/lib/features/shopping_cart/models/shopping_list.dart:33-55`
- Recipe books screen (pattern reference for list index): `app/lib/features/recipe_books/recipe_books_screen.dart`
- `broadcast_event_to_list` broadcast pattern from recipe router: `services/api/src/routers/v1/recipe_router.py:76-90`
- Story 7.4 (WebSocket pattern reference): `_bmad-output/implementation-artifacts/7-4-real-time-shared-book-updates.md`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Fixed `datetime.UTC` → `timezone.utc` in `update_item.py` and `delete_item.py` (Python < 3.11 compat)
- `Endpoint.call()` body is the raw data dict — no `["data"]` wrapper needed when parsing with `json.loads(result.body)`
- `ShoppingList.fromJson` null name fixed: `json['name'] as String? ?? ''`
- Code review fixes: `TextEditingController.dispose()` in `_createList`/`_joinList`, sort by `updated_at`, `id` assertion in broadcast test, `datetime.utcnow()` → `datetime.now(timezone.utc)` in `websocket.py`

### File List

- Modified: `services/api/src/api/v1/shopping_list/list_shopping_lists.py`
- Modified: `services/api/src/api/v1/shopping_list/update_item.py`
- Modified: `services/api/src/api/v1/shopping_list/delete_item.py`
- Modified: `services/api/src/api/v1/shopping_list/websocket.py`
- Modified: `services/api/src/routers/v1/shopping_list_router.py`
- Modified: `app/lib/features/cart/cart_screen.dart`
- Modified: `app/lib/features/shopping_cart/models/shopping_list.dart`
- Modified: `app/lib/core/router/app_router.dart`
- New: `services/api/tests/test_shopping_list_router_broadcasts.py`
- New: `app/test/features/cart/cart_screen_test.dart`
- New: `app/test/features/shopping_cart/shopping_list_model_test.dart`
