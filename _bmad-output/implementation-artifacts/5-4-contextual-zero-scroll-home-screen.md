# Story 5.4: Contextual Zero-Scroll Home Screen

Status: done

## Story

As a user,
I want the home screen to show me the right recipe before I search — based on what's planned, what I've cooked recently, and what I love,
So that most sessions start and end without needing to search at all.

## Acceptance Criteria

1. **Given** I open the app **When** the home screen loads **Then** I see a conditional hero card at the top if a meal is planned for today (large photo, Playfair Display title, "Start Cooking" CTA).
2. **Given** no meal is planned for today **When** the home screen loads **Then** the hero card is absent and the persistent search bar is the top element.
3. **Given** a meal is planned for today **When** it has a recipe attached **Then** the hero card shows the recipe image (edge-to-edge, 220h), recipe name in Playfair Display serif, and a "Start Cooking" button that navigates to cooking mode.
4. **Given** recently cooked recipes exist **When** the home screen loads **Then** a "Recently Cooked" section appears as a horizontal scroll of recipe cards below the hero/search area.
5. **Given** the user has cooked at least one recipe **When** viewing recently cooked **Then** cards show recipe image, name, and relative date (e.g., "2 days ago").
6. **Given** the home screen loads **When** there are favorite recipes **Then** the existing "Favorites" horizontal section appears.
7. **Given** the home screen loads **When** a request to meal-events or cooking-logs fails **Then** those sections are silently omitted (no error shown) and the rest of the home screen renders normally.
8. **Given** any meal event / cooking log sections are loading **When** the main recipe grid is already loaded **Then** the sections appear progressively without blocking the main grid.

## Tasks / Subtasks

- [x] Task 1: Backend — GET /v1/cooking-logs endpoint (AC: #4, #5)
  - [x] Create `services/api/src/api/v1/cooking_log/list_cooking_logs.py` with `ListCookingLogs` use case returning recently cooked recipes (joined with Recipe, last N distinct recipes by `cooked_at`)
  - [x] Create `services/api/src/routers/v1/cooking_log_router.py` with `GET /v1/cooking-logs` route
  - [x] Register router in `services/api/src/routers/v1_router.py`
  - [x] Add `ListCookingLogsResponse` Pydantic model with `items: list[CookingLogItem]` where `CookingLogItem` has `recipe_id`, `recipe_name`, `recipe_image_url`, `cooked_at`
  - [x] Add unit tests in `services/api/tests/test_cooking_logs.py`

- [x] Task 2: ApiClient — add meal events and cooking logs methods (AC: #1, #2, #3, #4)
  - [x] Add `getMealEventsForToday()` in `app/lib/core/services/api_client.dart` — calls `GET /v1/meal-events?start_date=TODAY&end_date=TODAY&status=planned&limit=1` and returns the first planned event with a recipe
  - [x] Add `getRecentlyCookedRecipes({int limit = 5})` — calls `GET /v1/cooking-logs?limit={limit}` and returns list of recently cooked items

- [x] Task 3: Flutter — home screen hero card (AC: #1, #2, #3)
  - [x] Add `dynamic _todayMealEvent` state variable (null = no planned meal today)
  - [x] Add `_loadHomeContext()` async method: calls `getMealEventsForToday()` and `getRecentlyCookedRecipes()` in parallel; on failure silently sets to null/empty
  - [x] Call `_loadHomeContext()` from `initState()` in parallel with `_loadRecipes()`
  - [x] Add `_buildHeroCard()` returning a widget with: edge-to-edge Image.network (height 220), Playfair Display recipe name overlay via GoogleFonts.playfairDisplay(), "Start Cooking" FilledButton that calls `_quickStartCooking()`; when no image, show surfaceContainerHighest placeholder with restaurant icon
  - [x] In `build()`: insert `_buildHeroCard()` above MealFilterBar when `_todayMealEvent != null`

- [x] Task 4: Flutter — recently cooked section (AC: #4, #5)
  - [x] Add `List<dynamic> _recentlyCooked = []` state variable
  - [x] Add `_buildRecentlyCookedSection()` returning a Column with a "Recently Cooked" heading and a 110h horizontal ListView of cards showing recipe image, name, and `_formatRelativeDate()` formatted date
  - [x] In `build()`: insert `_buildRecentlyCookedSection()` after hero card (or after search bar if no hero) when `_recentlyCooked.isNotEmpty`

- [x] Task 5: Tests (AC: all)
  - [x] Add `test_cooking_logs.py` API test: `GET /v1/cooking-logs` returns 200 with correct response shape
  - [x] Add `search_screen_test.dart`-style widget tests in `app/test/home_screen_context_test.dart`: hero card renders with recipe name; recently cooked card shows recipe name and relative date; absent when empty
  - [x] Run `npx nx run api:test` (227 passed) and `flutter test app/test/home_screen_context_test.dart` (5 passed) — all passing

## Dev Notes

### Backend: /v1/cooking-logs

The `CookingLog` model (`libraries/utils/utils/models/cooking_log.py`) has:
- `id`, `cooked_at` (DateTime with tz), `recipe_id` (FK), `pantry_id` (FK)
- `recipe` relationship — join to get `recipe.name`, `recipe.image_url`

Query pattern (SQLAlchemy 2.0 async, same style as all other list endpoints):
```python
# Get last N distinct recipes by most recent cooked_at
stmt = (
    select(CookingLog)
    .options(selectinload(CookingLog.recipe))
    .where(CookingLog.owner_id == current_user.id)  # ← CHECK if owner_id exists on model
    .order_by(CookingLog.cooked_at.desc())
    .limit(limit)
)
```

**IMPORTANT**: Check `cooking_log.py` for exact column names — the model may not have `owner_id`. If it uses `pantry_id` to scope to the user, join through pantry. Alternatively the `recipe.recipe_book.owner_id` chain can be used. Look at how other endpoints scope to the current user (e.g., `list_favorites.py` or `list_meal_events.py`).

Router pattern — match existing convention in `services/api/src/routers/v1/`:
```python
@router.get("", response_model=success(ListCookingLogsResponse))
async def list_cooking_logs(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success(await ListCookingLogs(db).execute(current_user=current_user, limit=limit))
```

Register in `services/api/src/main.py` exactly like `meal_event_router`:
```python
from api.routers.v1 import cooking_log_router
app.include_router(cooking_log_router.router, prefix="/v1/cooking-logs", tags=["cooking-logs"])
```

### Backend: List Meal Events (already exists)

`GET /v1/meal-events` already handles `start_date`, `end_date`, `status` params. No backend changes needed for the hero card — the Flutter client just passes today's date.

Response shape (from `list_meal_events.py`):
```json
{
  "data": {
    "items": [{ "id": "...", "recipe": {"id":"..","name":"..","image_url":".."}, "scheduled_at":"..","status":"planned", ... }],
    "total": 1, "limit": 1, "offset": 0
  }
}
```

### Flutter: ApiClient additions

File: `app/lib/core/services/api_client.dart`

```dart
Future<Response> getMealEventsForToday() {
  final today = DateTime.now().toIso8601String().substring(0, 10); // YYYY-MM-DD
  return _dio.get('/v1/meal-events', queryParameters: {
    'start_date': today,
    'end_date': today,
    'status': 'planned',
    'limit': 1,
  });
}

Future<Response> getRecentlyCookedRecipes({int limit = 5}) {
  return _dio.get('/v1/cooking-logs', queryParameters: {'limit': limit});
}
```

### Flutter: Home Screen changes

File: `app/lib/features/home/home_screen.dart` (currently 616 lines)

**State additions** (add alongside existing `_favorites`, `_isLoading`):
```dart
dynamic _todayMealEvent; // null = no planned meal today
List<dynamic> _recentlyCooked = [];
```

**_loadHomeContext()** — fire and forget from `initState()`:
```dart
Future<void> _loadHomeContext() async {
  try {
    final results = await Future.wait([
      _apiClient.getMealEventsForToday(),
      _apiClient.getRecentlyCookedRecipes(),
    ]);
    if (!mounted) return;
    final mealData = results[0].data['data']['items'] as List?;
    final cookData = results[1].data['data']['items'] as List?;
    setState(() {
      _todayMealEvent = (mealData != null && mealData.isNotEmpty && mealData[0]['recipe'] != null)
          ? mealData[0]
          : null;
      _recentlyCooked = cookData ?? [];
    });
  } catch (_) {
    // silently ignore — home screen works without this context
  }
}
```

In `initState()`, add `_loadHomeContext()` call alongside existing `_loadRecipes()`.

**_buildHeroCard()** design spec:
- Height 220, full width, `ClipRRect` with `borderRadius: BorderRadius.zero`
- Stack: CachedNetworkImage as background, gradient overlay at bottom, recipe name in Playfair Display 24px white bold, "Start Cooking" FilledButton in warm primary color
- Fallback: Container with `Theme.of(context).colorScheme.surfaceVariant`, Icon(Icons.restaurant, size: 64)
- Tap on card OR "Start Cooking" button: call `_quickStartCooking(recipeId)` — navigate to cooking mode (existing pattern)

**_buildRecentlyCookedSection()** design:
- `Column` with `Padding(padding: EdgeInsets.fromLTRB(16, 16, 16, 0))` heading "Recently Cooked" in `titleMedium` style
- `SizedBox(height: 110)` containing horizontal `ListView.builder` of recipe cards (80w x 100h) — each card shows thumbnail, recipe name, timeago date
- Use `timeago` package if already available; otherwise format manually as "X days ago"

**Build method changes** — minimal, insert new sections:
```dart
// In build() Column children, between search header and MealFilterBar:
if (_todayMealEvent != null) _buildHeroCard(),
if (_recentlyCooked.isNotEmpty) _buildRecentlyCookedSection(),
```

### Existing patterns to follow

1. **Recipe card pattern**: look at `_buildFavoritesSection()` — same card style for recently cooked
2. **CachedNetworkImage**: already used in recipe cards throughout the app — same import and usage
3. **Playfair Display**: used in title texts — `TextStyle(fontFamily: 'PlayfairDisplay', fontSize: 24, fontWeight: FontWeight.bold)`
4. **Navigation to cooking mode**: `_quickStartCooking(recipeId)` — already implemented, just pass `_todayMealEvent['recipe']['id']`
5. **Silent error handling**: `_loadRecipes()` sets `_error` state — `_loadHomeContext()` must NOT set `_error`, just swallow exceptions
6. **`mounted` check after async**: critical — all setState calls after await must check `if (!mounted) return`

### Testing

**API test** (`services/api/tests/test_cooking_logs.py`):
```python
class TestCookingLogs:
    def test_list_cooking_logs_success(self, client, mock_db, mock_user):
        mock_db.db.execute.return_value = MockExecuteResult([])
        response = client.get("/v1/cooking-logs")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data["data"]

    def test_list_cooking_logs_with_limit(self, client, mock_db, mock_user):
        mock_db.db.execute.return_value = MockExecuteResult([])
        response = client.get("/v1/cooking-logs?limit=3")
        assert response.status_code == 200
```

**Flutter tests** (`app/test/home_screen_context_test.dart`) — widget-level isolation, same pattern as `search_screen_test.dart`:
```dart
testWidgets('hero card renders recipe name', (tester) async {
  // Build isolated HeroCard-equivalent widget with recipe name text
  // Verify text renders
});
testWidgets('recently cooked card shows recipe name', (tester) async {
  // Build isolated card widget
  // Verify recipe name and date text render
});
```

### Project Structure Notes

- New files follow existing naming: `list_cooking_logs.py` (use case), `cooking_log_router.py` (router)
- Router registered in `main.py` following exact pattern of other routers (see `meal_event_router` registration)
- Flutter feature location: `app/lib/features/home/home_screen.dart` — extend existing file, do NOT create separate files for `_buildHeroCard()` / `_buildRecentlyCookedSection()`; they're internal to the screen
- Tests in `services/api/tests/test_cooking_logs.py` and `app/test/home_screen_context_test.dart`

### References

- [Source: libraries/utils/utils/models/cooking_log.py] — CookingLog model fields
- [Source: libraries/utils/utils/models/meal_event.py] — MealEvent model fields
- [Source: services/api/src/api/v1/meal_event/list_meal_events.py] — ListMealEvents use case pattern
- [Source: services/api/src/routers/v1/meal_event_router.py] — Router registration pattern
- [Source: app/lib/core/services/api_client.dart] — All existing API client methods
- [Source: app/lib/features/home/home_screen.dart] — Existing home screen (616 lines)
- [Source: _bmad-output/planning-artifacts/epics.md#5.4] — AC, user story
- [Source: _bmad-output/planning-artifacts/architecture.md] — Riverpod patterns, dio usage

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implemented `GET /v1/cooking-logs` endpoint scoping to user via `Recipe → RecipeBookUser` join (CookingLog has no owner_id)
- Router registration via `v1_router.py` aggregator (not `main.py` — corrected from story notes)
- `_loadHomeContext()` fires silently in parallel with `_loadRecipes()` in initState; all failures swallowed
- `_buildHeroCard()` uses `GoogleFonts.playfairDisplay()` for recipe name; `Image.network` (not CachedNetworkImage) to match existing pattern
- `_formatRelativeDate()` helper added to home_screen.dart for relative date formatting without external dependency
- 227 API tests pass; 5 Flutter widget tests pass; no regressions

### File List

- services/api/src/api/v1/cooking_log/__init__.py
- services/api/src/api/v1/cooking_log/list_cooking_logs.py
- services/api/src/routers/v1/cooking_log_router.py
- services/api/src/routers/v1_router.py
- services/api/tests/test_cooking_logs.py
- app/lib/core/services/api_client.dart
- app/lib/features/home/home_screen.dart
- app/test/home_screen_context_test.dart
