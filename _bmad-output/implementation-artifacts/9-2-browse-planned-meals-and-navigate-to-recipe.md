# Story 9.2: Browse Planned Meals & Navigate to Recipe

Status: done

## Story

As a user,
I want to view upcoming planned meals with timing info and jump straight to the recipe,
So that I can quickly see what's coming up and start cooking.

## Acceptance Criteria

1. **Prep time on calendar tiles** — Each planned meal tile in `CalendarScreen` shows prep time (e.g., "20 min prep") when the recipe has a `prep_time` value. If both `prep_time` and `cook_time` exist, show total time (prep + cook).
2. **Tap navigates to recipe** — Tapping a meal tile navigates to `/recipes/{recipe_id}`. (Already implemented in 9.1 — must remain working.)
3. **Home screen hero card shows tonight's meal** — The home screen hero card already shows the planned recipe name and image. Enhance it to also display total prep+cook time (e.g., "45 min total") when available.
4. **Past meals visible as cooking log** — Week navigation allows scrolling to previous weeks. Past meal tiles render identically to upcoming ones (no special visual treatment required — they remain on the calendar as a log).
5. **Empty state** — Days with no planned meals show "No meals planned" with a subtle prompt to use "Plan for..." from a recipe. (Already implemented in 9.1 — must remain working.)

## Tasks / Subtasks

- [x] Task 1: Extend `RecipeSummary` model to capture `prep_time` and `cook_time` (AC: 1, 3)
  - [x] Add `prepTime` (`int?`) and `cookTime` (`int?`) fields to `RecipeSummary` in `app/lib/features/calendar/models/meal_event.dart`
  - [x] Update `RecipeSummary.fromJson` to parse `prep_time` and `cook_time` from JSON
  - [x] Add `totalMinutes` convenience getter: `(prepTime ?? 0) + (cookTime ?? 0)`, returns `null` if both are zero/null

- [x] Task 2: Display prep/total time on calendar event tiles (AC: 1)
  - [x] Update `_buildEventTile` in `CalendarScreen` to show timing info below the meal type chip
  - [x] Format: if `totalMinutes > 0`, show `"{n} min"` using a small muted Text widget
  - [x] Only show timing row when `event.recipe?.totalMinutes != null && event.recipe!.totalMinutes! > 0`

- [x] Task 3: Add timing info to home screen hero card (AC: 3)
  - [x] In `home_screen.dart` `_buildHeroCard()`, read `prep_time` and `cook_time` from `_todayMealEvent!['recipe']`
  - [x] Compute total = `(prep_time ?? 0) + (cook_time ?? 0)`
  - [x] If total > 0, display `"{total} min"` as a small chip/tag above the "Start Cooking" button
  - [x] Styling: use a semi-transparent white chip consistent with the hero card overlay aesthetic

- [x] Task 4: Flutter widget tests (AC: 1, 3)
  - [x] Add tests to `app/test/features/calendar/calendar_screen_test.dart`:
    - [x] Test: event tile shows prep time when recipe has `prepTime` set
    - [x] Test: event tile hides timing row when `prepTime` and `cookTime` are both null
  - [x] Add tests to `app/test/features/home/home_screen_test.dart` (or new file if it doesn't exist):
    - [x] Test: hero card displays prep time when `prep_time` is in the meal event response

## Dev Notes

### What is Already Implemented (from Story 9.1)

**`RecipeSummary` model** (`app/lib/features/calendar/models/meal_event.dart`):
```dart
class RecipeSummary {
  final String id;
  final String name;
  final String? imageUrl;
  // NOTE: backend returns prep_time and cook_time but they are NOT yet in this model
}
```

**Backend API response** — BOTH create and list endpoints already include `prep_time` and `cook_time` in the recipe summary:
```python
# services/api/src/api/v1/meal_event/create_meal_event.py and list_meal_events.py
class RecipeSummary(BaseModel):
    id: str
    name: str
    description: str | None = None
    prep_time: int | None = None     # ← already returned, Flutter ignores it
    cook_time: int | None = None     # ← already returned, Flutter ignores it
    image_url: str | None = None
```

**CalendarScreen event tile** (`app/lib/features/calendar/calendar_screen.dart`):
- Currently shows: thumbnail, title, meal type chip, chevron
- New: add timing row below meal type chip

**Home screen hero card** (`app/lib/features/home/home_screen.dart`):
- `getMealEventsForToday()` in `ApiClient` fetches today's meal (limit=1, status=planned)
- `_todayMealEvent` stores the raw JSON map (not `MealEvent` model — raw `Map<String, dynamic>`)
- `_buildHeroCard()` reads `_todayMealEvent!['recipe']` directly as a map
- Currently shows: recipe name, background image, "Start Cooking" button
- Raw recipe map already contains `prep_time` and `cook_time` — just need to read and display them

### Extended `RecipeSummary` Model

```dart
// app/lib/features/calendar/models/meal_event.dart

class RecipeSummary {
  final String id;
  final String name;
  final String? imageUrl;
  final int? prepTime;    // minutes, from prep_time
  final int? cookTime;    // minutes, from cook_time

  const RecipeSummary({
    required this.id,
    required this.name,
    this.imageUrl,
    this.prepTime,
    this.cookTime,
  });

  int? get totalMinutes {
    final total = (prepTime ?? 0) + (cookTime ?? 0);
    return total > 0 ? total : null;
  }

  factory RecipeSummary.fromJson(Map<String, dynamic> json) => RecipeSummary(
    id: json['id'] as String,
    name: json['name'] as String,
    imageUrl: json['image_url'] as String?,
    prepTime: json['prep_time'] as int?,
    cookTime: json['cook_time'] as int?,
  );
}
```

### Calendar Tile Timing Row

Add below the meal type chip in `_buildEventTile`:

```dart
// After the meal type chip Container:
if (event.recipe?.totalMinutes != null) ...[
  const SizedBox(height: 2),
  Text(
    '${event.recipe!.totalMinutes} min',
    style: const TextStyle(
      fontSize: 11,
      color: AppColors.textDisabled,
    ),
  ),
],
```

### Home Screen Hero Card Timing

In `_buildHeroCard()`, the recipe is accessed as a raw map. Add the timing display:

```dart
Widget _buildHeroCard() {
  final recipe = _todayMealEvent!['recipe'];
  final prepTime = recipe['prep_time'] as int? ?? 0;
  final cookTime = recipe['cook_time'] as int? ?? 0;
  final totalMinutes = prepTime + cookTime;
  // ...
  // Before the "Start Cooking" FilledButton, add:
  if (totalMinutes > 0)
    Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.25),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        '$totalMinutes min',
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
      ),
    ),
  const SizedBox(height: 8),
}
```

### Home Screen Test Pattern

The home screen uses `_apiClient.getMealEventsForToday()` — use `GetIt` to register a fake `ApiClient` or use the existing home screen test setup if it exists. Check for an existing `app/test/features/home/home_screen_test.dart`.

If no existing test file, create a minimal one following the same pattern as `calendar_screen_test.dart`: register a fake or mock service, pump the widget, and assert the timing text is visible.

### No Backend Changes Required

The backend already returns `prep_time` and `cook_time` in all meal event responses. This story is entirely frontend work.

### Testing Pattern (from Story 9.1)

For calendar tests — use `_FakeMealCalendarService` with `RecipeSummary` that has `prepTime` set:

```dart
final event = MealEvent(
  id: 'e1',
  title: 'Pasta Night',
  scheduledAt: DateTime.now(),
  mealType: MealType.dinner,
  status: 'planned',
  isShared: true,
  ownerId: 'u1',
  recipe: RecipeSummary(
    id: 'r1',
    name: 'Pasta Carbonara',
    imageUrl: null,
    prepTime: 15,
    cookTime: 20,
  ),
);
// Expect: find.text('35 min') findsOneWidget
```

### Project Structure Notes

- Modified files:
  - `app/lib/features/calendar/models/meal_event.dart` — add `prepTime`, `cookTime`, `totalMinutes` to `RecipeSummary`
  - `app/lib/features/calendar/calendar_screen.dart` — add timing row in `_buildEventTile`
  - `app/lib/features/home/home_screen.dart` — add timing chip in `_buildHeroCard`
- Test files:
  - `app/test/features/calendar/calendar_screen_test.dart` — add 2 timing tests
  - `app/test/features/home/home_screen_test.dart` — add hero card timing test (create if doesn't exist)

### References

- Epic 9 story 9.2: `_bmad-output/planning-artifacts/epics.md`
- RecipeSummary model: `app/lib/features/calendar/models/meal_event.dart`
- CalendarScreen event tile: `app/lib/features/calendar/calendar_screen.dart:310–388`
- Home screen hero card: `app/lib/features/home/home_screen.dart:571–645`
- Backend RecipeSummary schema (includes prep_time/cook_time): `services/api/src/api/v1/meal_event/create_meal_event.py`
- AppColors: `app/lib/core/theme/app_colors.dart`
- Story 9.1 for all calendar infrastructure: `_bmad-output/implementation-artifacts/9-1-schedule-recipes-to-meal-calendar.md`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- ✅ Task 1: Extended `RecipeSummary` with `prepTime`, `cookTime` (parsed from `prep_time`/`cook_time` JSON), and `totalMinutes` getter (sum, null if zero)
- ✅ Task 2: Added timing row in `_buildEventTile` — shows `"{n} min"` below meal type chip when `totalMinutes != null`
- ✅ Task 3: Added timing chip in `_buildHeroCard` — semi-transparent white chip above "Start Cooking" button; only shown when `prepTime + cookTime > 0`
- ✅ Task 4: 4 Flutter widget tests — 2 calendar screen (shows/hides timing), 2 home screen hero card (shows timing, hides timing when absent); all 399 Flutter tests pass, 329 backend tests pass

### File List

- `app/lib/features/calendar/models/meal_event.dart` — added `prepTime`, `cookTime`, `totalMinutes` to `RecipeSummary`
- `app/lib/features/calendar/calendar_screen.dart` — added timing row in `_buildEventTile`
- `app/lib/features/home/home_screen.dart` — added timing chip in `_buildHeroCard`
- `app/test/features/calendar/calendar_screen_test.dart` — added 2 timing tests
- `app/test/features/home/home_screen_test.dart` — new file with 2 hero card timing tests
