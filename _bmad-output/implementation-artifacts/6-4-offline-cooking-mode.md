# Story 6.4: Offline Cooking Mode

Status: review

## Story

As a user,
I want cooking mode to work fully offline with cached recipe data,
So that I can cook reliably even with poor kitchen Wi-Fi.

## Acceptance Criteria

1. Given I have previously viewed a recipe while online, When I enter cooking mode without network connectivity, Then all recipe data (ingredients, steps) loads from local cache
2. Step navigation, timers, and the ingredient strip all function offline (they already do — the only failure point is initial load)
3. A subtle offline indicator appears in the cook mode header (not alarming — small icon + "Offline")
4. Any note additions made offline (e.g., from post-cook feedback in Story 6.5) are queued in a persistent local queue and sync when connectivity returns

## Tasks / Subtasks

- [x] Task 1: Add dependencies (AC: #1, #4)
  - [x] Add `shared_preferences: ^2.3.4` to `app/pubspec.yaml` dependencies
  - [x] Add `connectivity_plus: ^6.1.4` to `app/pubspec.yaml` dependencies
  - [x] Run `flutter pub get` from `app/` directory

- [x] Task 2: Create `RecipeCacheService` (AC: #1, #4)
  - [x] Create `app/lib/core/services/recipe_cache_service.dart`
  - [x] `cacheRecipe(String recipeId, Map<String, dynamic> data)`: serializes recipe to JSON via `jsonEncode`, stores under key `palateful_recipe_$recipeId` in SharedPreferences
  - [x] `loadCachedRecipe(String recipeId)`: loads from SharedPreferences, returns `Map<String, dynamic>?` (null if not cached)
  - [x] `hasCachedRecipe(String recipeId)`: checks key existence in SharedPreferences
  - [x] `queueNoteAdd(String recipeId, String body)`: appends JSON-encoded `{recipe_id, body, queued_at}` to SharedPreferences list key `palateful_pending_notes`
  - [x] `getPendingNotes()`: returns `List<Map<String, dynamic>>` of queued notes
  - [x] `clearPendingNotes()`: removes the pending notes key from SharedPreferences (call after successful sync)
  - [x] Register in `app/lib/core/di/injection.dart` as `getIt.registerLazySingleton<RecipeCacheService>(() => RecipeCacheService())`

- [x] Task 3: Update `CookModeScreen._loadRecipe()` for offline fallback (AC: #1, #2, #3)
  - [x] Add `bool _isOffline = false` state variable to `_CookModeScreenState`
  - [x] Add `final _recipeCache = getIt<RecipeCacheService>()` field
  - [x] In `_loadRecipe()`: wrap API call in try/catch; on success, call `_recipeCache.cacheRecipe(widget.recipeId, response.data)` before `setState`
  - [x] In the catch block: detect if error is a connectivity/network failure (check `DioException` type `DioExceptionType.connectionError` / `connectionTimeout` / `sendTimeout` / `receiveTimeout`); if so, attempt `_recipeCache.loadCachedRecipe(widget.recipeId)` — if found, populate `_recipe`, `_ingredients`, `_steps` from cache and `setState(() { _isOffline = true; _isLoading = false; })`
  - [x] If error is connectivity failure AND no cache exists, show error state: "No cached recipe. Connect to internet to load this recipe."
  - [x] Non-connectivity errors (4xx, 5xx) continue to show the existing error state

- [x] Task 4: Show offline indicator in header (AC: #3)
  - [x] In `_buildHeader()`, add offline indicator widget when `_isOffline == true`
  - [x] Render as: small `Icon(Icons.wifi_off, size: 14, color: AppColors.terracotta)` + `Text('Offline', style: TextStyle(fontSize: 11, color: AppColors.terracotta))` — subtle, not alarming
  - [x] Place it between recipe name and cooking timer in the header Row

- [x] Task 5: Sync pending notes on connectivity restore (AC: #4)
  - [x] In `didChangeAppLifecycleState(resumed)`: after timer reconciliation, call `_syncPendingNotes()`
  - [x] Implement `_syncPendingNotes()`: checks connectivity (via `Connectivity().checkConnectivity()`), if connected, fetches `_recipeCache.getPendingNotes()`, for each pending note calls `_apiClient.addRecipeNote(note['recipe_id'], note['body'])`, on all success calls `_recipeCache.clearPendingNotes()`, silently catches errors (no-op if fails, will retry next resume)
  - [x] Set `_isOffline = false` on successful sync (call `setState` if mounted)

- [x] Task 6: Widget tests (AC: #1–#4)
  - [x] Create `app/test/offline_cook_mode_test.dart`
  - [x] Test: `RecipeCacheService.cacheRecipe` stores data under correct key
  - [x] Test: `RecipeCacheService.loadCachedRecipe` returns null for unknown recipe
  - [x] Test: `RecipeCacheService.loadCachedRecipe` returns data after `cacheRecipe`
  - [x] Test: `RecipeCacheService.queueNoteAdd` appends to pending notes list
  - [x] Test: offline indicator widget renders correctly when `_isOffline == true`
  - [x] 5+ tests, all must pass

## Dev Notes

### This Is a Brownfield Story — Do NOT Rewrite CookModeScreen

`CookModeScreen` uses pure `setState` — no Riverpod. Keep it that way. The architecture doc specifies "Riverpod offline persistence" as the long-term goal, but this story adds offline caching via `shared_preferences` to the existing setState pattern. Do NOT introduce Riverpod into `CookModeScreen` for this story.

The codebase pattern is: stateful widgets with direct `getIt` DI calls. Follow it.

### Current `_loadRecipe` Pattern (Extend, Don't Rewrite)

```dart
Future<void> _loadRecipe() async {
  try {
    final response = await _apiClient.getRecipe(widget.recipeId);
    if (mounted) {
      final recipe = response.data;
      setState(() {
        _recipe = recipe;
        _ingredients = recipe['ingredients'] ?? [];
        final stepsData = ...sort and map...
        _steps = stepsData...;
        _isLoading = false;
      });
    }
  } catch (e) {
    if (mounted) {
      setState(() {
        _error = 'Failed to load recipe: $e';
        _isLoading = false;
      });
    }
  }
}
```

**New pattern — detect network failure vs. other errors:**

```dart
Future<void> _loadRecipe() async {
  try {
    final response = await _apiClient.getRecipe(widget.recipeId);
    // Cache on successful fetch
    await _recipeCache.cacheRecipe(widget.recipeId, response.data as Map<String, dynamic>);
    if (mounted) {
      _populateFromData(response.data);
    }
  } on DioException catch (e) {
    // Network failures → try cache
    if (_isNetworkError(e)) {
      final cached = await _recipeCache.loadCachedRecipe(widget.recipeId);
      if (cached != null && mounted) {
        setState(() { _isOffline = true; });
        _populateFromData(cached);
        return;
      }
      // No cache + no network
      if (mounted) setState(() { _error = 'No cached data. Connect to internet and retry.'; _isLoading = false; });
    } else {
      if (mounted) setState(() { _error = 'Failed to load recipe: $e'; _isLoading = false; });
    }
  } catch (e) {
    if (mounted) setState(() { _error = 'Failed to load recipe: $e'; _isLoading = false; });
  }
}

bool _isNetworkError(DioException e) {
  return e.type == DioExceptionType.connectionError ||
         e.type == DioExceptionType.connectionTimeout ||
         e.type == DioExceptionType.sendTimeout ||
         e.type == DioExceptionType.receiveTimeout;
}

void _populateFromData(Map<String, dynamic> recipe) {
  final stepsData = List<dynamic>.from(recipe['steps'] as List? ?? []);
  stepsData.sort((a, b) =>
      (a['step_number'] as int? ?? 0).compareTo(b['step_number'] as int? ?? 0));
  setState(() {
    _recipe = recipe;
    _ingredients = recipe['ingredients'] ?? [];
    _steps = stepsData
        .map((s) => s['instruction'] as String? ?? '')
        .where((s) => s.isNotEmpty)
        .toList();
    _isLoading = false;
  });
}
```

### Offline Indicator — Subtle, Not Alarming

Per UX spec: dark cook mode theme. Offline indicator should:
- Use `AppColors.terracotta` (warm, not error-red)
- Be small (14px icon, 11px text)
- Sit in the header between recipe name and cooking time
- NOT block any functionality

```dart
// In _buildHeader() Row, add after recipe name Expanded:
if (_isOffline) ...[
  const SizedBox(width: 8),
  Row(
    mainAxisSize: MainAxisSize.min,
    children: const [
      Icon(Icons.wifi_off, size: 14, color: AppColors.terracotta),
      SizedBox(width: 2),
      Text('Offline', style: TextStyle(fontSize: 11, color: AppColors.terracotta)),
    ],
  ),
],
```

### `RecipeCacheService` — Key Design Decisions

**Why SharedPreferences, not Hive/sqflite?**
- No new native dependencies — SharedPreferences is pure Dart/Flutter
- Recipe JSON fits comfortably in SharedPreferences (typical recipe < 50KB)
- Consistent with the simple service pattern used throughout the codebase

**Cache Invalidation — Not Required for This Story**
- Recipe data is cached once on successful load, overwritten on next successful load
- No TTL or manual invalidation needed — cook mode is read-only; the cache is always updated when online
- If recipe is updated by another device, the cook will get stale data — acceptable trade-off for the simple pattern

**Pending Notes Queue — Infrastructure for Story 6.5**
- Story 6.5 (Post-Cook Feedback) will add notes via the feedback flow
- If the user finishes cooking offline, notes should queue rather than silently drop
- `RecipeCacheService` provides `queueNoteAdd` / `getPendingNotes` / `clearPendingNotes` as infrastructure
- Story 6.5 should call `queueNoteAdd` instead of direct API when offline, and `CookModeScreen.didChangeAppLifecycleState` calls `_syncPendingNotes()` to flush the queue

**Connectivity Check Pattern:**
```dart
import 'package:connectivity_plus/connectivity_plus.dart';

Future<bool> _isConnected() async {
  final result = await Connectivity().checkConnectivity();
  return !result.contains(ConnectivityResult.none);
}
```

Note: `connectivity_plus` returns a `List<ConnectivityResult>` in v6+, not a single value.

### `shared_preferences` Key Namespace

All keys use `palateful_` prefix to avoid collisions:
- `palateful_recipe_{recipeId}` — cached recipe JSON
- `palateful_pending_notes` — JSON-encoded list of pending note additions

### Cook Mode Does NOT Render Photos

The current `CookModeScreen` has no `Image.network` or `CachedNetworkImage` calls — it's text-only (ingredients strip, step text). The AC mentions "photos" but cook mode doesn't display photos currently. No photo caching work is needed for this story. Photos are displayed in the recipe detail screen (`recipe_detail_screen.dart`) which uses `Image.network` — that is out of scope for this story.

### DioException vs Generic Exception

`ApiClient` uses `dio` which throws `DioException` for network errors. Always catch `DioException` before the generic `catch (e)` clause.

```dart
on DioException catch (e) {
  // Network error handling
} catch (e) {
  // Generic error handling
}
```

### Connectivity Plus v6+ API Change

In `connectivity_plus` v6+, `checkConnectivity()` returns `List<ConnectivityResult>` (not a single value):
```dart
// ✓ Correct v6+ pattern
final results = await Connectivity().checkConnectivity();
final isOnline = !results.contains(ConnectivityResult.none);

// ✗ Wrong — v5 pattern (single value)
final result = await Connectivity().checkConnectivity();
final isOnline = result != ConnectivityResult.none;
```

### Testing `RecipeCacheService`

Use `shared_preferences` test stub:
```dart
import 'package:shared_preferences/shared_preferences.dart';

setUp(() {
  SharedPreferences.setMockInitialValues({});
});
```

### Existing File — DO NOT Touch These Files

- `app/lib/features/recipes/recipe_detail_screen.dart` — out of scope
- `app/lib/core/services/cook_timer_notification_service.dart` — out of scope
- Any backend Python files — offline is purely client-side

### References

- [Source: app/lib/features/recipes/cook_mode/cook_mode_screen.dart] — File to extend: `_loadRecipe()`, `_buildHeader()`, `didChangeAppLifecycleState`
- [Source: app/lib/core/di/injection.dart] — DI registration pattern
- [Source: app/lib/core/services/cook_timer_notification_service.dart] — Service registration pattern to follow
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Architecture] — "Caching: Redis (server) + Riverpod offline persistence (client)"
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture] — `cached_network_image` for photo caching (already in pubspec)
- [Source: _bmad-output/implementation-artifacts/6-3-concurrent-timers-with-background-notifications.md] — Connectivity to cook mode, `didChangeAppLifecycleState`, DI patterns established
- [pubspec.yaml] — `cached_network_image: ^3.4.1` already present; `connectivity_plus` and `shared_preferences` must be added

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

- `RecipeCacheService` uses `shared_preferences` in-memory stub in tests (`SharedPreferences.setMockInitialValues({})`) — no platform channel needed.
- `_populateFromData()` helper extracted to avoid code duplication between online and offline paths.
- `_syncPendingNotes()` silently catches all errors — retry on next app resume is the correct pattern for this use case.
- connectivity_plus v6+ `checkConnectivity()` returns `List<ConnectivityResult>` — used `.contains(ConnectivityResult.none)` correctly.
- 9 tests written and passing (7 service unit tests + 2 indicator widget tests).

### File List

- app/pubspec.yaml
- app/lib/core/services/recipe_cache_service.dart (NEW)
- app/lib/core/di/injection.dart
- app/lib/features/recipes/cook_mode/cook_mode_screen.dart
- app/test/offline_cook_mode_test.dart (NEW)
