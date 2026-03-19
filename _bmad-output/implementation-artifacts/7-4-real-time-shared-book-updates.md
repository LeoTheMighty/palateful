# Story 7.4: Real-Time Shared Book Updates

Status: done

## Story

As a user,
I want to see real-time updates when my partner adds, edits, or forks recipes in our shared books,
So that our shared collection feels alive and collaborative.

## Acceptance Criteria

1. **Given** I am viewing a shared recipe book screen, **When** another member adds a recipe, **Then** the new recipe appears in my list without manual refresh.

2. **Given** I am viewing a shared recipe book screen, **When** another member edits or archives a recipe in that book, **Then** my view updates automatically to reflect the change.

3. **Given** I am viewing a shared recipe book screen, **When** another member forks a recipe into that book, **Then** the forked recipe appears in my list.

4. **Given** I am viewing a shared recipe book, **When** the real-time connection is established, **Then** a subtle "live" indicator is visible (green dot or similar).

5. **Given** the WebSocket connection drops, **When** I am still on the recipe book screen, **Then** the app reconnects automatically with exponential back-off and the list refreshes on reconnect.

6. **Given** I am viewing a personal (non-shared) recipe book, **Then** no WebSocket connection is opened (no-op for non-shared books).

## Tasks / Subtasks

- [x] Task 1: Backend — WebSocket handler for recipe books (AC: 1, 2, 3)
  - [x] 1.1 Create `services/api/src/api/v1/recipe_book/websocket.py` with `RecipeBookConnectionManager` and `recipe_book_websocket_handler` following the shopping list WebSocket pattern exactly
  - [x] 1.2 Export `recipe_book_websocket_handler` and `broadcast_event_to_recipe_book` from `services/api/src/api/v1/recipe_book/__init__.py`
  - [x] 1.3 Add WebSocket route to `services/api/src/routers/v1/recipe_book_router.py`: `@recipe_book_router.websocket("/ws/{book_id}")` (resolves to `/recipe-books/ws/{book_id}` under the `/v1` prefix)

- [x] Task 2: Backend — Broadcast recipe mutations to connected book clients (AC: 1, 2, 3)
  - [x] 2.1 In `services/api/src/routers/v1/recipe_router.py`, import `broadcast_event_to_recipe_book` from the recipe_book websocket module
  - [x] 2.2 After `CreateRecipe.call(...)`, call `await broadcast_event_to_recipe_book(book_id, "recipe_added", {...recipe data...}, user_id)` — but only if book_id is known
  - [x] 2.3 After `UpdateRecipe.call(...)`, call `await broadcast_event_to_recipe_book(book_id, "recipe_updated", {...})`
  - [x] 2.4 After `DeleteRecipe.call(...)` (archive), call `await broadcast_event_to_recipe_book(book_id, "recipe_removed", {"recipe_id": recipe_id})`
  - [x] 2.5 After `ForkRecipe.call(...)`, call `await broadcast_event_to_recipe_book(dest_book_id, "recipe_added", {...})` — fork adds to destination book
  - [x] 2.6 The router handlers are `async def`, so calling `await broadcast_event_to_recipe_book(...)` is correct; however the `Endpoint.call()` return value is a `JSONResponse` — extract `recipe_book_id` from the request params OR from the response data

- [x] Task 3: Backend — Tests (AC: 1–3)
  - [x] 3.1 Create `services/api/tests/test_recipe_book_websocket.py` with tests for: connect/disconnect (auth validated), broadcast sends to all connected clients, non-member connection is rejected (4003)
  - [x] 3.2 All existing tests must continue to pass (`npx nx run api:test`)

- [x] Task 4: Flutter — RecipeBookSyncService (AC: 1–5)
  - [x] 4.1 Create `app/lib/features/recipe_books/services/recipe_book_sync_service.dart` modeled directly on `ShoppingCartService` in `app/lib/features/shopping_cart/services/shopping_cart_service.dart`
  - [x] 4.2 Service exposes streams: `onRecipeAdded`, `onRecipeUpdated`, `onRecipeRemoved` (each carrying `Map<String,dynamic>`)
  - [x] 4.3 Service exposes `connectionState` getter and `onConnectionStateChange` stream
  - [x] 4.4 WebSocket URL: `${apiClient.wsBaseUrl}/v1/recipe-books/ws/$bookId?token=$token` (note: prefix is `/recipe-books/ws/` not `/ws/recipe-books/`)
  - [x] 4.5 Reconnect with 5-second delay on error/disconnect; ping every 30 seconds
  - [x] 4.6 Register in DI: add `getIt.registerLazySingleton<RecipeBookSyncService>(() => RecipeBookSyncService())` in `app/lib/core/di/injection.dart`

- [x] Task 5: Flutter — Integrate into RecipeBookDetailScreen (AC: 1–6)
  - [x] 5.1 In `_RecipeBookDetailScreenState`, obtain `RecipeBookSyncService` from DI
  - [x] 5.2 In `initState`, if `_isShared`, call `_syncService.connectWebSocket(widget.recipeBookId)`; keep `StreamSubscription` references
  - [x] 5.3 Subscribe to `onRecipeAdded`: add the new recipe map to `_recipes` via `setState`
  - [x] 5.4 Subscribe to `onRecipeUpdated`: find matching recipe by id, replace in `_recipes` via `setState`
  - [x] 5.5 Subscribe to `onRecipeRemoved`: remove recipe by id from `_recipes` via `setState`
  - [x] 5.6 Subscribe to `onConnectionStateChange`: update a local `_wsConnected` bool; show a green dot indicator in the AppBar title area when connected (visible only for shared books)
  - [x] 5.7 In `dispose`, cancel all subscriptions and call `_syncService.disconnectWebSocket()` (or disconnect for this book_id)
  - [x] 5.8 Personal books (`!_isShared`): skip WS connection entirely

- [x] Task 6: Flutter — Tests (AC: 1–6)
  - [x] 6.1 Create `app/test/features/recipe_books/recipe_book_sync_service_test.dart` — unit tests for service event dispatch
  - [x] 6.2 Create `app/test/features/recipe_books/recipe_book_detail_realtime_test.dart` — widget test: mock service, fire `onRecipeAdded`, verify new recipe card appears; fire `onRecipeRemoved`, verify removal

## Dev Notes

### Critical Architecture: WebSocket Pattern (follow shopping list exactly)

The existing real-time pattern uses `web_socket_channel` (already in `pubspec.yaml`) with raw WebSocket connections — **NOT** AppSync/amplify_flutter. The architecture doc mentions AppSync as an intent but the codebase uses native FastAPI WebSockets. Follow the existing pattern.

**Reference implementation**: `services/api/src/api/v1/shopping_list/websocket.py` + `app/lib/features/shopping_cart/services/shopping_cart_service.dart`

### Backend: WebSocket Handler Pattern

The `RecipeBookConnectionManager` in `websocket.py` should be an exact parallel of `ConnectionManager` from the shopping list:

```python
class RecipeBookConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, set[tuple[str, WebSocket]]] = {}
        self.connection_info: dict[WebSocket, tuple[str, set[str]]] = {}

    async def connect(self, websocket, user, book_id) -> bool: ...
    def disconnect(self, websocket): ...
    async def broadcast_to_book(self, book_id, message, exclude_websocket=None): ...
    def get_online_users(self, book_id) -> list[str]: ...

manager = RecipeBookConnectionManager()
```

The `recipe_book_websocket_handler(websocket, book_id, user, db)` validates access via `RecipeBookUser` table (user must have membership). Auth via JWT token query param identical to shopping list.

### Backend: WebSocket Route Placement

The `recipe_book_router` has `prefix="/recipe-books"`. Adding the WS route as:
```python
@recipe_book_router.websocket("/ws/{book_id}")
```
Results in final URL: `wss://host/v1/recipe-books/ws/{book_id}?token=JWT`

Flutter client URL: `${apiClient.wsBaseUrl}/v1/recipe-books/ws/$bookId?token=$token`

### Backend: Broadcast From Recipe Router

The recipe mutation endpoints are in `recipe_router.py`. The route handlers are `async def`, so they can `await` the broadcast. Get the `recipe_book_id` from:
- CreateRecipe: from `params.recipe_book_id`
- UpdateRecipe: from the endpoint response data (`response['recipe_book_id']`)
- DeleteRecipe (archive): from the response or from fetching before deletion
- ForkRecipe: from `params.destination_book_id`

Pattern in the router:
```python
from api.v1.recipe_book.websocket import broadcast_event_to_recipe_book

@recipe_router.post("/recipes", status_code=201)
async def create_recipe(params: CreateRecipe.Params, ...):
    result = CreateRecipe.call(params=params, user=user, database=database)
    # Broadcast to all book members' WS connections
    await broadcast_event_to_recipe_book(
        str(params.recipe_book_id),
        "recipe_added",
        result.body  # JSONResponse body bytes — parse with json.loads OR pass result data explicitly
    )
    return result
```

**Note on JSONResponse body**: `Endpoint.call()` returns a `fastapi.responses.JSONResponse`. To get the data for broadcasting, either:
a) Re-read the response body: `import json; data = json.loads(result.body)`
b) Or have the endpoint return a simple dict and convert to JSONResponse in the router (more refactoring)
c) **Recommended**: Pass the relevant IDs/minimal data directly from `params` without parsing the response body

The broadcast payload for `recipe_added` only needs: `{"recipe_id": ..., "recipe_book_id": ..., "name": ...}`. The receiving client will re-fetch the full recipe book or update the list with what's available.

Actually the simplest approach: have the Flutter client just re-call `_loadRecipeBook()` when ANY recipe mutation event arrives, rather than trying to merge individual fields. This avoids needing a complete recipe payload in the WebSocket message.

### Frontend: Service Structure

`RecipeBookSyncService` mirrors `ShoppingCartService`:
```dart
class RecipeBookSyncService {
  WebSocketChannel? _wsChannel;
  StreamSubscription? _wsSubscription;
  Timer? _reconnectTimer, _pingTimer;
  String? _currentBookId;

  final _recipeAddedController = StreamController<Map<String,dynamic>>.broadcast();
  final _recipeUpdatedController = StreamController<Map<String,dynamic>>.broadcast();
  final _recipeRemovedController = StreamController<String>.broadcast();
  final _connectionStateController = StreamController<WebSocketState>.broadcast();

  Stream<Map<String,dynamic>> get onRecipeAdded => _recipeAddedController.stream;
  ...

  void connectWebSocket(String bookId) { ... }
  void disconnectWebSocket() { ... }
  void dispose() { ... }
}
```

Re-use `WebSocketState` enum from `ShoppingCartService` OR define it locally — pick one, avoid duplication.

**Recommendation**: Extract `WebSocketState` to a shared file `app/lib/core/services/websocket_state.dart` and import it in both services. This prevents duplicating the enum.

### Frontend: Integration in RecipeBookDetailScreen

In `_RecipeBookDetailScreenState`:
```dart
late final RecipeBookSyncService _syncService;
StreamSubscription? _addedSub, _updatedSub, _removedSub, _stateSub;
bool _wsConnected = false;

@override
void initState() {
  super.initState();
  _syncService = getIt<RecipeBookSyncService>();
  _loadRecipeBook();
}

void _subscribeToRealTime() {
  // Only called after _isShared is known = true
  _syncService.connectWebSocket(widget.recipeBookId);
  _addedSub = _syncService.onRecipeAdded.listen((recipe) {
    if (!mounted) return;
    setState(() => _recipes.add(recipe));
  });
  _updatedSub = _syncService.onRecipeUpdated.listen((recipe) {
    if (!mounted) return;
    setState(() {
      final idx = _recipes.indexWhere((r) => r['id'] == recipe['id']);
      if (idx >= 0) _recipes[idx] = recipe;
    });
  });
  _removedSub = _syncService.onRecipeRemoved.listen((recipeId) {
    if (!mounted) return;
    setState(() => _recipes.removeWhere((r) => r['id'] == recipeId));
  });
  _stateSub = _syncService.onConnectionStateChange.listen((state) {
    if (!mounted) return;
    setState(() => _wsConnected = state == WebSocketState.connected);
  });
}

@override
void dispose() {
  _addedSub?.cancel(); _updatedSub?.cancel();
  _removedSub?.cancel(); _stateSub?.cancel();
  _syncService.disconnectWebSocket();
  super.dispose();
}
```

Call `_subscribeToRealTime()` from `_loadRecipeBook()` after setting `_isShared = true`.

**Prevent double-subscription**: Guard with a `_subscribed` flag so re-calling `_loadRecipeBook()` doesn't re-subscribe.

### Live Indicator

In the AppBar for shared books, show a small dot next to the title:
```dart
title: Row(children: [
  Text(_recipeBook?['name'] ?? 'Recipe Book'),
  if (_isShared) ...[
    const SizedBox(width: 8),
    Container(
      width: 8, height: 8,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: _wsConnected ? Colors.green : Colors.grey,
      ),
    ),
  ],
]),
```

### No Database Migration Needed

The WebSocket connection manager is purely in-memory. No new tables or columns required for this story.

### Testing Approach

**Backend** (`test_recipe_book_websocket.py`): Use FastAPI's `TestClient` with WebSocket support. Reference existing shopping list tests if any, or create minimal tests:
- `test_websocket_rejects_unauthenticated`: connect without token, expect close code 4001
- `test_websocket_rejects_non_member`: connect with valid token for user not in book, expect 4003
- `test_broadcast_recipe_added_to_connected_clients`: mock two connections, trigger broadcast, verify both receive message

**Flutter** tests: Use `StreamController` to simulate `RecipeBookSyncService` in widget tests. Inject mock service via DI overrides.

### Project Structure Notes

- New file: `services/api/src/api/v1/recipe_book/websocket.py`
- Modified: `services/api/src/api/v1/recipe_book/__init__.py` (add 2 exports)
- Modified: `services/api/src/routers/v1/recipe_book_router.py` (add WS route + WebSocket import)
- Modified: `services/api/src/routers/v1/recipe_router.py` (add broadcast calls)
- New file: `app/lib/features/recipe_books/services/recipe_book_sync_service.dart`
- New file: `app/lib/core/services/websocket_state.dart` (shared `WebSocketState` enum, ONLY if it avoids duplication — if not needed, skip)
- Modified: `app/lib/features/recipe_books/recipe_book_detail_screen.dart` (subscribe, live indicator)
- Modified: `app/lib/core/di/injection.dart` (register `RecipeBookSyncService`)
- New test: `services/api/tests/test_recipe_book_websocket.py`
- New test: `app/test/features/recipe_books/recipe_book_detail_realtime_test.dart`

### References

- Shopping list WebSocket backend: `services/api/src/api/v1/shopping_list/websocket.py`
- Shopping cart service: `app/lib/features/shopping_cart/services/shopping_cart_service.dart`
- Shopping list router WS route: `services/api/src/routers/v1/shopping_list_router.py:422-470`
- Recipe book router (has prefix `/recipe-books`): `services/api/src/routers/v1/recipe_book_router.py`
- Recipe router (recipe CRUD): `services/api/src/routers/v1/recipe_router.py`
- RecipeBookUser model: `libraries/utils/utils/models/recipe_book_user.py`
- ApiClient wsBaseUrl: `app/lib/core/services/api_client.dart:357-360`
- DI registration: `app/lib/core/di/injection.dart`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Backend WebSocket handler follows shopping list pattern exactly (in-memory connection manager, no DB migration)
- `RecipeBookSyncService` constructor-injected for testability; falls back to `getIt<ApiClient>()` in production
- `_subscribed` guard in `RecipeBookDetailScreen` prevents double-subscription on `_loadRecipeBook()` re-calls
- `cook_timer_notification_service.dart` pre-existing compile errors fixed (missing `flutter/widgets.dart` import and required `uiLocalNotificationDateInterpretation` param)
- All 271 backend tests pass; all Flutter tests pass

### File List

- `services/api/src/api/v1/recipe_book/websocket.py` (new)
- `services/api/src/api/v1/recipe_book/__init__.py` (modified)
- `services/api/src/routers/v1/recipe_book_router.py` (modified)
- `services/api/src/routers/v1/recipe_router.py` (modified)
- `services/api/tests/test_recipe_book_websocket.py` (new)
- `app/lib/features/recipe_books/services/recipe_book_sync_service.dart` (new)
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` (modified)
- `app/lib/core/di/injection.dart` (modified)
- `app/lib/core/services/cook_timer_notification_service.dart` (modified — pre-existing compile fixes)
- `app/test/features/recipe_books/recipe_book_sync_service_test.dart` (new)
- `app/test/features/recipe_books/recipe_book_detail_realtime_test.dart` (new)
