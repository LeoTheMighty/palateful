# Story 9.1: Schedule Recipes to Meal Calendar

Status: done

## Story

As a user,
I want to schedule recipes to specific dates on a shared meal calendar,
So that my household knows what we're cooking this week.

## Acceptance Criteria

1. **"Plan for..." entry point on recipe detail** — The recipe detail overflow menu contains a "Plan for..." option. Tapping it opens `PlanMealSheet`.
2. **Date + meal-slot picker** — `PlanMealSheet` lets the user pick a date (date picker) and meal type (breakfast / lunch / dinner / snack). Tapping "Save" calls `POST /v1/meal-events` with `recipe_id`, the chosen `scheduled_at`, and `meal_type`; the sheet closes on success with a success snackbar.
3. **Calendar week view shows planned meals** — `CalendarScreen` renders a 7-day week strip. Each day column lists the meal events scheduled for that day, showing the recipe thumbnail (or a meal-type icon if no photo) and title. Tapping the row navigates to the recipe detail screen.
4. **Partner sees planned meals** — `is_shared` defaults to `true` when creating via "Plan for..." so household partners see the event. (Household partners already share recipe books — shared events are returned by `ListMealEvents` for all participants.)
5. **Remove planned meal** — Long-pressing a calendar event shows a "Remove" option. Tapping it calls `DELETE /v1/meal-events/{event_id}` and removes the event from the calendar.
6. **Reschedule planned meal** — Tapping on a calendar event (not long-press) opens `PlanMealSheet` in edit mode, pre-filled with current date/time and meal type. Saving calls `PUT /v1/meal-events/{event_id}` and refreshes the calendar.
7. **Week navigation** — The calendar header shows left/right arrows to navigate to the previous/next week. Default view is the current week.

## Tasks / Subtasks

- [x] Task 1: Add `MealEvent` model and `MealCalendarService` (AC: 3, 5, 6)
  - [x] Create `app/lib/features/calendar/models/meal_event.dart` — `MealEvent`, `RecipeSummary`, `MealType` enum
  - [x] Create `app/lib/features/calendar/services/meal_calendar_service.dart` — `listMealEvents(startDate, endDate)`, `createMealEvent(...)`, `updateMealEvent(eventId, ...)`, `deleteMealEvent(eventId)`

- [x] Task 2: Add API client methods for meal event CRUD (AC: 2, 5, 6)
  - [x] Add `listMealEventsForRange(DateTime start, DateTime end)` to `api_client.dart`
  - [x] Add `createMealEvent(Map<String, dynamic> data)` to `api_client.dart`
  - [x] Add `updateMealEvent(String eventId, Map<String, dynamic> data)` to `api_client.dart`
  - [x] Add `deleteMealEvent(String eventId)` to `api_client.dart`

- [x] Task 3: Build `PlanMealSheet` (AC: 2, 6)
  - [x] Create `app/lib/features/calendar/widgets/plan_meal_sheet.dart`
  - [x] Date picker row (shows today by default, opens `showDatePicker`)
  - [x] Meal type selector (4 chips: Breakfast / Lunch / Dinner / Snack, defaults to Dinner)
  - [x] Save button calls `MealCalendarService.createMealEvent` or `updateMealEvent` depending on whether `eventId` is provided
  - [x] Shows success snackbar and closes on success; shows error snackbar on failure

- [x] Task 4: Build `CalendarScreen` week view (AC: 3, 5, 6, 7)
  - [x] Replace placeholder `app/lib/features/calendar/calendar_screen.dart` with full implementation
  - [x] Header: current week label (e.g. "Mar 16–22") + left/right arrows to navigate weeks
  - [x] 7-column day strip with day name + day number; today's column highlighted
  - [x] Each day column lists `MealEventTile` widgets for scheduled events
  - [x] `MealEventTile`: shows recipe thumbnail (CircleAvatar with `image_url` or meal-type icon), recipe title or event title, meal-type chip
  - [x] Tapping a tile navigates to `/recipes/{recipe_id}` (if event has `recipe_id`)
  - [x] Long-pressing a tile shows bottom sheet with "Reschedule" and "Remove" options
  - [x] Loads events for the displayed week on init and on week navigation

- [x] Task 5: Add "Plan for..." to recipe detail overflow menu (AC: 1, 2)
  - [x] Add `'plan'` case to `PopupMenuButton.onSelected` in `recipe_detail_screen.dart`
  - [x] Add `PopupMenuItem(value: 'plan', ...)` with `Icons.calendar_today_outlined` and text "Plan for..."
  - [x] On select: show `PlanMealSheet(recipeId: widget.recipeId, recipeName: _recipe!['name'])`

- [x] Task 6: Backend tests for meal event schedule flow (AC: 2, 4, 5, 6)
  - [x] Create `services/api/tests/test_schedule_meal.py`
  - [x] Test: `create_meal_event_with_recipe_id_returns_recipe_summary` — recipe summary populated in response
  - [x] Test: `create_meal_event_with_invalid_recipe_id_returns_404`
  - [x] Test: `list_meal_events_date_range_filter` — start_date/end_date excludes out-of-range events
  - [x] Test: `delete_meal_event_removes_it` — DELETE returns 200, event no longer returned by GET
  - [x] Test: `update_meal_event_reschedules` — PUT updates `scheduled_at` and `meal_type`
  - [x] Test: `non_owner_cannot_delete_meal_event` — 403

- [x] Task 7: Flutter widget tests (AC: 2, 3, 5)
  - [x] Create `app/test/features/calendar/plan_meal_sheet_test.dart`
  - [x] Test: renders date row and 4 meal type chips
  - [x] Test: selecting "Lunch" chip highlights it and deselects others
  - [x] Test: Save button calls `onSave` callback with correct `meal_type`
  - [x] Create `app/test/features/calendar/calendar_screen_test.dart`
  - [x] Test: displays 7 day columns for the current week
  - [x] Test: meal event tile renders recipe title
  - [x] Test: today's column is visually highlighted

## Dev Notes

### What is Already Implemented

**Backend (fully functional):**
- `CreateMealEvent` (`services/api/src/api/v1/meal_event/create_meal_event.py`):
  - `POST /v1/meal-events` — Params: `title`, `scheduled_at`, `meal_type`, `recipe_id` (optional), `is_shared`, `is_recurring`; verifies recipe exists if provided; creates owner `MealEventParticipant` with `role="host"`; returns 201 with recipe summary
- `ListMealEvents` (`services/api/src/api/v1/meal_event/list_meal_events.py`):
  - `GET /v1/meal-events` — query params: `start_date`, `end_date`, `meal_type`, `status`, `limit`, `offset`; returns events the user owns OR participates in; `scheduled_at` ordered; returns recipe summaries
- `UpdateMealEvent` (`services/api/src/api/v1/meal_event/update_meal_event.py`):
  - `PUT /v1/meal-events/{event_id}` — can update `scheduled_at`, `meal_type`, `recipe_id`, `status`, `is_shared`; owner/cohost only
- `DeleteMealEvent` (`services/api/src/api/v1/meal_event/delete_meal_event.py`):
  - `DELETE /v1/meal-events/{event_id}` — owner only; returns 403 otherwise

**Flutter API client (partial):**
- `getMealEventsForToday()` (`app/lib/core/services/api_client.dart:484–492`): fetches today's planned events; used by home screen. **Missing:** create, update, delete, list-by-range

**Flutter calendar:**
- `CalendarScreen` (`app/lib/features/calendar/calendar_screen.dart`): **Fully placeholder** — just shows empty state. Route `/calendar` is already wired.

**No Flutter models or service for meal events in the calendar feature** — only the API call exists.

**Existing backend test coverage** (`services/api/tests/test_meal_event.py`): basic list/create/get/delete happy paths. Missing: recipe_id validation, date-range filter, reschedule, is_shared logic.

### MealEvent Model

```dart
// app/lib/features/calendar/models/meal_event.dart

enum MealType { breakfast, lunch, dinner, snack }

class RecipeSummary {
  final String id;
  final String name;
  final String? imageUrl;

  const RecipeSummary({required this.id, required this.name, this.imageUrl});

  factory RecipeSummary.fromJson(Map<String, dynamic> json) => RecipeSummary(
    id: json['id'] as String,
    name: json['name'] as String,
    imageUrl: json['image_url'] as String?,
  );
}

class MealEvent {
  final String id;
  final String title;
  final DateTime scheduledAt;
  final MealType mealType;
  final String status;
  final bool isShared;
  final RecipeSummary? recipe;
  final String ownerId;

  const MealEvent({
    required this.id,
    required this.title,
    required this.scheduledAt,
    required this.mealType,
    required this.status,
    required this.isShared,
    this.recipe,
    required this.ownerId,
  });

  factory MealEvent.fromJson(Map<String, dynamic> json) => MealEvent(
    id: json['id'] as String,
    title: json['title'] as String,
    scheduledAt: DateTime.parse(json['scheduled_at'] as String),
    mealType: MealType.values.firstWhere(
      (m) => m.name == json['meal_type'],
      orElse: () => MealType.dinner,
    ),
    status: json['status'] as String,
    isShared: json['is_shared'] as bool,
    recipe: json['recipe'] != null
        ? RecipeSummary.fromJson(json['recipe'] as Map<String, dynamic>)
        : null,
    ownerId: json['owner_id'] as String,
  );
}
```

### MealCalendarService

```dart
// app/lib/features/calendar/services/meal_calendar_service.dart

class MealCalendarService {
  final ApiClient _apiClient;
  MealCalendarService(this._apiClient);

  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end) async {
    final response = await _apiClient.listMealEventsForRange(start, end);
    final items = (response.data['items'] as List).cast<Map<String, dynamic>>();
    return items.map(MealEvent.fromJson).toList();
  }

  Future<MealEvent> createMealEvent({
    required String title,
    required DateTime scheduledAt,
    required MealType mealType,
    String? recipeId,
    bool isShared = true,
  }) async {
    final response = await _apiClient.createMealEvent({
      'title': title,
      'scheduled_at': scheduledAt.toIso8601String(),
      'meal_type': mealType.name,
      if (recipeId != null) 'recipe_id': recipeId,
      'is_shared': isShared,
    });
    return MealEvent.fromJson(response.data as Map<String, dynamic>);
  }

  Future<MealEvent> updateMealEvent(
    String eventId, {
    required DateTime scheduledAt,
    required MealType mealType,
  }) async {
    final response = await _apiClient.updateMealEvent(eventId, {
      'scheduled_at': scheduledAt.toIso8601String(),
      'meal_type': mealType.name,
    });
    return MealEvent.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteMealEvent(String eventId) async {
    await _apiClient.deleteMealEvent(eventId);
  }
}
```

### API Client Methods to Add

```dart
// In app/lib/core/services/api_client.dart, under "Meal events" section:

Future<Response> listMealEventsForRange(DateTime start, DateTime end) {
  return _dio.get('/v1/meal-events', queryParameters: {
    'start_date': start.toIso8601String().substring(0, 10),
    'end_date': end.toIso8601String().substring(0, 10),
    'limit': 50,
  });
}

Future<Response> createMealEvent(Map<String, dynamic> data) {
  return _dio.post('/v1/meal-events', data: data);
}

Future<Response> updateMealEvent(String eventId, Map<String, dynamic> data) {
  return _dio.put('/v1/meal-events/$eventId', data: data);
}

Future<Response> deleteMealEvent(String eventId) {
  return _dio.delete('/v1/meal-events/$eventId');
}
```

### PlanMealSheet Usage

```dart
// From recipe_detail_screen.dart, in PopupMenuButton.onSelected:
} else if (value == 'plan') {
  _planForDate();
}

// New method:
void _planForDate() {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    builder: (_) => PlanMealSheet(
      recipeId: widget.recipeId,
      recipeName: _recipe!['name'] as String,
    ),
  );
}
```

### CalendarScreen Week View Structure

The screen maintains:
- `_weekStart`: Monday of displayed week (compute from `DateTime.now()` minus weekday offset)
- `_events`: `Map<DateTime, List<MealEvent>>` keyed by date (time stripped)
- Loads on init and on week change

Week navigation:
```dart
DateTime get _weekEnd => _weekStart.add(const Duration(days: 6));

void _previousWeek() => setState(() {
  _weekStart = _weekStart.subtract(const Duration(days: 7));
  _loadEvents();
});

void _nextWeek() => setState(() {
  _weekStart = _weekStart.add(const Duration(days: 7));
  _loadEvents();
});
```

### Backend Test Pattern

Follows pattern from `test_check_off_items.py`. Use `MockMealEvent` and `MockRecipe` from conftest.

For date-range test:
```python
def test_list_meal_events_date_range_filter(self, client, mock_db, mock_user):
    in_range = MockMealEvent(
        owner_id=str(mock_user.id),
        scheduled_at=datetime(2026, 3, 18, 19, 0, tzinfo=UTC),
    )
    # Return only the in-range event from the mock query
    mock_db.db.query.return_value = MockQuery([in_range])
    response = client.get("/v1/meal-events?start_date=2026-03-16&end_date=2026-03-22")
    assert response.status_code == 200
    assert response.json()["total"] == 1
```

### DI Registration

`MealCalendarService` should be registered in `app/lib/core/di/injection.dart` alongside other services:
```dart
getIt.registerLazySingleton<MealCalendarService>(
  () => MealCalendarService(getIt<ApiClient>()),
);
```

### Flutter Test Pattern

Use a minimal `FakeMealCalendarService` (simple class, no Mockito) for widget tests:

```dart
class _FakeMealCalendarService implements MealCalendarService {
  final List<MealEvent> events;
  _FakeMealCalendarService({this.events = const []});

  @override
  Future<List<MealEvent>> listMealEvents(DateTime start, DateTime end) async => events;

  @override
  Future<MealEvent> createMealEvent({...}) async => ...;
  // etc.
}
```

For `PlanMealSheet` tests — pure widget tests, pass `onSave` callback to capture calls:
```dart
String? savedMealType;
await tester.pumpWidget(MaterialApp(
  home: Scaffold(body: PlanMealSheet(
    recipeId: 'r1',
    recipeName: 'Pasta',
    onSave: ({required mealType, required date}) {
      savedMealType = mealType.name;
    },
  )),
));
```

### Project Structure Notes

- New files:
  - `app/lib/features/calendar/models/meal_event.dart`
  - `app/lib/features/calendar/services/meal_calendar_service.dart`
  - `app/lib/features/calendar/widgets/plan_meal_sheet.dart`
  - `services/api/tests/test_schedule_meal.py`
  - `app/test/features/calendar/plan_meal_sheet_test.dart`
  - `app/test/features/calendar/calendar_screen_test.dart`
- Modified files:
  - `app/lib/features/calendar/calendar_screen.dart` — full week view implementation
  - `app/lib/core/services/api_client.dart` — add CRUD methods for meal events
  - `app/lib/core/di/injection.dart` — register `MealCalendarService`
  - `app/lib/features/recipes/recipe_detail_screen.dart` — add "Plan for..." menu item

### References

- Epic 9 story 9.1 requirements: `_bmad-output/planning-artifacts/epics.md:1005–1019`
- Backend create endpoint: `services/api/src/api/v1/meal_event/create_meal_event.py`
- Backend list endpoint: `services/api/src/api/v1/meal_event/list_meal_events.py`
- Backend update endpoint: `services/api/src/api/v1/meal_event/update_meal_event.py`
- Backend delete endpoint: `services/api/src/api/v1/meal_event/delete_meal_event.py`
- Existing test coverage: `services/api/tests/test_meal_event.py`
- Placeholder CalendarScreen: `app/lib/features/calendar/calendar_screen.dart`
- API client (add methods here): `app/lib/core/services/api_client.dart:483`
- Recipe detail overflow menu: `app/lib/features/recipes/recipe_detail_screen.dart:489`
- Router calendar route: `app/lib/core/router/app_router.dart:346`
- DI injection: `app/lib/core/di/injection.dart`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- ✅ Task 1: Created `MealEvent` model with `MealType` enum and `RecipeSummary`; `MealCalendarService` with full CRUD wrapping the API client
- ✅ Task 2: Added `listMealEventsForRange`, `createMealEvent`, `updateMealEvent`, `deleteMealEvent` to `api_client.dart`; registered `MealCalendarService` in DI
- ✅ Task 3: Built `PlanMealSheet` — date picker row, 4 meal-type chips (defaults to Dinner), create/edit mode, success/error snackbars
- ✅ Task 4: Replaced placeholder `CalendarScreen` with 7-day week view using `SingleChildScrollView+Column`; today highlighted, event tiles with thumbnail/icon, long-press options (Reschedule/Remove), week navigation arrows
- ✅ Task 5: Added `'Plan for...'` popup menu item to `recipe_detail_screen.dart`; opens `PlanMealSheet` with recipe ID and name
- ✅ Task 6: 10 backend tests in `test_schedule_meal.py` covering create-with-recipe, invalid-recipe 404, create-without-recipe, date-range list, empty-range list, delete success, delete 403, delete 404, reschedule, non-owner update 403 — 329 total backend tests pass
- ✅ Task 7: 18 Flutter widget tests across `plan_meal_sheet_test.dart` (layout, chip selection, initial values, save) and `calendar_screen_test.dart` (7 day columns, event tile, today highlight, meal type chip, navigation) — all pass; `ListView` → `SingleChildScrollView+Column` to ensure all 7 day cards render in test viewport

### Senior Developer Review (AI)

### File List

- `app/lib/features/calendar/models/meal_event.dart` — MealEvent model, RecipeSummary, MealType enum
- `app/lib/features/calendar/services/meal_calendar_service.dart` — MealCalendarService with CRUD
- `app/lib/features/calendar/widgets/plan_meal_sheet.dart` — PlanMealSheet bottom sheet widget
- `app/lib/features/calendar/calendar_screen.dart` — full week view (replaced placeholder)
- `app/lib/core/services/api_client.dart` — added listMealEventsForRange, createMealEvent, updateMealEvent, deleteMealEvent
- `app/lib/core/di/injection.dart` — registered MealCalendarService
- `app/lib/features/recipes/recipe_detail_screen.dart` — added "Plan for..." menu item and _planForDate method
- `services/api/tests/test_schedule_meal.py` — 10 backend tests for schedule flow
- `app/test/features/calendar/plan_meal_sheet_test.dart` — 10 Flutter widget tests for PlanMealSheet
- `app/test/features/calendar/calendar_screen_test.dart` — 8 Flutter widget tests for CalendarScreen
