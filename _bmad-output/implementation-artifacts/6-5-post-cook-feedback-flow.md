# Story 6.5: Post-Cook Feedback Flow

Status: done

## Story

As a user,
I want to be prompted for quick feedback after finishing cooking mode,
So that I can capture how it went and add notes while the experience is fresh.

## Acceptance Criteria

1. Given I reach the last step and tap "Done cooking", When cooking mode ends, Then I see a brief feedback bottom sheet: 5-star rating selector + optional notes text field
2. When I save the feedback, Then the cook is logged locally (date, recipe, rating) via `RecipeCacheService.logCook()`
3. When I add a note in the feedback flow, Then the note is submitted to the recipe via `POST /v1/recipes/{id}/notes` (or queued offline via `RecipeCacheService.queueNoteAdd()` if no connectivity)
4. I can skip the feedback flow entirely — a "Skip" button dismisses without saving and exits cook mode
5. After saving or skipping, the flow transitions back to the recipe detail screen (`context.pop()` from CookModeScreen)

## Tasks / Subtasks

- [x] Task 1: Extend `RecipeCacheService` with cook log storage (AC: #2)
  - [x] Add `static const _cookLogsKeyPrefix = 'palateful_cook_logs_'` constant
  - [x] Add `logCook(String recipeId, int rating, DateTime cookedAt)`: appends `{recipe_id, rating, cooked_at}` entry to SharedPreferences list under key `palateful_cook_logs_{recipeId}`
  - [x] Add `getCookLogs(String recipeId)`: returns `List<Map<String, dynamic>>` of stored cook log entries for that recipe (empty list if none)

- [x] Task 2: Create `PostCookFeedbackSheet` widget (AC: #1, #2, #3, #4)
  - [x] Create `app/lib/features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart`
  - [x] `PostCookFeedbackSheet` is a `StatefulWidget` with params: `recipeId`, `recipeName`, `apiClient`, `recipeCache`, `isOffline`, `onComplete` callback
  - [x] State: `int _selectedRating = 0` (0 = no star selected), `TextEditingController _notesController`, `bool _isSaving = false`
  - [x] Render: dark sheet (no AppBar), drag handle at top, heading "How did it go?", subtitle = `recipeName`, 5-star rating row, notes TextField (optional, multiline), Save button + Skip button
  - [x] Star rating row: 5 `IconButton`s — icon is `Icons.star` (filled) when `_selectedRating >= i`, `Icons.star_border` (empty) otherwise, `color: AppColors.terracotta`, `iconSize: 36`; tapping sets `_selectedRating = i`
  - [x] Notes field: hint "Add a note... (optional)", maxLines: 3, unfocusedBorderColor: `AppColors.chocolateLight`, focusedBorderColor: `AppColors.terracotta`, textColor: `AppColors.warmIvory`
  - [x] Save button: `FilledButton`, `backgroundColor: AppColors.terracotta`, label "Save", `minimumSize: Size.fromHeight(48)`, shows `CircularProgressIndicator` when `_isSaving`; disabled when `_isSaving`
  - [x] Skip button: `TextButton`, label "Skip", `foregroundColor: AppColors.withOpacity(AppColors.warmIvory, 0.6)`, `minimumSize: Size.fromHeight(48)`, calls `onComplete` directly (no saving)
  - [x] `_saveFeedback()` method:
    - If `_selectedRating > 0`: `await recipeCache.logCook(recipeId, _selectedRating, DateTime.now())`
    - If notes field not empty: if `!isOffline` → `await apiClient.addRecipeNote(recipeId, notes)`, else → `await recipeCache.queueNoteAdd(recipeId, notes)` (offline queue from Story 6.4)
    - Wrap in `try/catch` — silently continue on error (call `onComplete` regardless)
    - Always calls `onComplete` at end
  - [x] Wrap Save tap in `setState(() => _isSaving = true)` before call, but rely on `onComplete` to close sheet (no need to reset `_isSaving`)
  - [x] `dispose()` must call `_notesController.dispose()`

- [x] Task 3: Update `_finishCooking()` in `CookModeScreen` to show feedback sheet (AC: #1, #5)
  - [x] Replace current `_finishCooking()` body with: stop stopwatch, heavy haptic, call `_showPostCookFeedbackSheet()`
  - [x] Add `Future<void> _showPostCookFeedbackSheet()` method:
    ```dart
    await showModalBottomSheet<void>(
      context: context,
      isDismissible: false,
      enableDrag: false,
      isScrollControlled: true,
      backgroundColor: AppColors.chocolateDark,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetContext) => PostCookFeedbackSheet(
        recipeId: widget.recipeId,
        recipeName: _recipe?['name'] ?? 'Recipe',
        apiClient: _apiClient,
        recipeCache: _recipeCache,
        isOffline: _isOffline,
        onComplete: () => Navigator.of(sheetContext).pop(),
      ),
    );
    if (mounted) context.pop(); // Exit cook mode after feedback sheet closes
    ```
  - [x] Add import: `import 'widgets/post_cook_feedback_sheet.dart'`
  - [x] Remove the old SnackBar from `_finishCooking()` — the feedback sheet replaces it as the completion UX

- [x] Task 4: Widget tests (AC: #1–#5)
  - [x] Create `app/test/post_cook_feedback_test.dart`
  - [x] Test: `RecipeCacheService.logCook` stores entry under correct key
  - [x] Test: `RecipeCacheService.getCookLogs` returns empty list for unknown recipe
  - [x] Test: `RecipeCacheService.getCookLogs` returns logs after `logCook`
  - [x] Test: `PostCookFeedbackSheet` renders star rating (5 star icons visible)
  - [x] Test: Skip button fires `onComplete` without any data saved
  - [x] Test: Save button fires `onComplete` after selecting a rating
  - [x] 5+ tests, all must pass

## Dev Notes

### This Is a Brownfield Story — Do NOT Rewrite CookModeScreen

`CookModeScreen` uses pure `setState` — no Riverpod. Do NOT change this. Follow the same `getIt` DI pattern used by `_apiClient`, `_timerNotifService`, `_recipeCache`.

### Current `_finishCooking()` — Replace This

```dart
// CURRENT (to be replaced):
void _finishCooking() {
  _completedSteps.add(_currentStep);
  HapticFeedback.heavyImpact();
  ScaffoldMessenger.of(context).showSnackBar(
    const SnackBar(
      content: Text('Recipe completed! Great job! 🎉'),
      backgroundColor: AppColors.success,
      behavior: SnackBarBehavior.floating,
    ),
  );
  context.pop();
}

// NEW:
void _finishCooking() {
  _completedSteps.add(_currentStep);
  HapticFeedback.heavyImpact();
  _cookingStopwatch.stop();
  _showPostCookFeedbackSheet();
}

Future<void> _showPostCookFeedbackSheet() async {
  await showModalBottomSheet<void>(
    context: context,
    isDismissible: false,
    enableDrag: false,
    isScrollControlled: true,
    backgroundColor: AppColors.chocolateDark,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (sheetContext) => PostCookFeedbackSheet(
      recipeId: widget.recipeId,
      recipeName: _recipe?['name'] ?? 'Recipe',
      apiClient: _apiClient,
      recipeCache: _recipeCache,
      isOffline: _isOffline,
      onComplete: () => Navigator.of(sheetContext).pop(),
    ),
  );
  if (mounted) context.pop(); // Exit cook mode screen after sheet closes
}
```

**Why `isDismissible: false, enableDrag: false`?** The feedback sheet should not close accidentally via swipe. The Skip button is the intentional dismiss path. This prevents unintentional exit.

**Why `isScrollControlled: true`?** Allows the keyboard to push the sheet up when the user taps the notes field. Without this, the keyboard overlaps the notes text field.

### `PostCookFeedbackSheet` — Full Widget Spec

```dart
// app/lib/features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart

import 'package:flutter/material.dart';
import '../../../../core/services/api_client.dart';
import '../../../../core/services/recipe_cache_service.dart';
import '../../../../core/theme/app_colors.dart';

class PostCookFeedbackSheet extends StatefulWidget {
  final String recipeId;
  final String recipeName;
  final ApiClient apiClient;
  final RecipeCacheService recipeCache;
  final bool isOffline;
  final VoidCallback onComplete;

  const PostCookFeedbackSheet({
    super.key,
    required this.recipeId,
    required this.recipeName,
    required this.apiClient,
    required this.recipeCache,
    required this.isOffline,
    required this.onComplete,
  });

  @override
  State<PostCookFeedbackSheet> createState() => _PostCookFeedbackSheetState();
}

class _PostCookFeedbackSheetState extends State<PostCookFeedbackSheet> {
  int _selectedRating = 0;
  final _notesController = TextEditingController();
  bool _isSaving = false;

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _saveFeedback() async {
    setState(() => _isSaving = true);
    try {
      if (_selectedRating > 0) {
        await widget.recipeCache.logCook(
          widget.recipeId, _selectedRating, DateTime.now());
      }
      final notes = _notesController.text.trim();
      if (notes.isNotEmpty) {
        if (!widget.isOffline) {
          await widget.apiClient.addRecipeNote(widget.recipeId, notes);
        } else {
          await widget.recipeCache.queueNoteAdd(widget.recipeId, notes);
        }
      }
    } catch (_) {
      // Silently continue — feedback capture is best-effort
    }
    widget.onComplete();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
        24, 20, 24, MediaQuery.of(context).viewInsets.bottom + 36),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Drag handle (visual only — sheet is not draggable)
          Container(
            width: 40, height: 4,
            decoration: BoxDecoration(
              color: AppColors.withOpacity(AppColors.warmIvory, 0.3),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 20),
          const Text('How did it go?',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700,
              color: AppColors.warmIvory)),
          const SizedBox(height: 4),
          Text(widget.recipeName,
            style: const TextStyle(fontSize: 14, color: AppColors.cream),
            overflow: TextOverflow.ellipsis),
          const SizedBox(height: 20),

          // 5-star rating
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(5, (i) {
              final star = i + 1;
              return IconButton(
                icon: Icon(
                  _selectedRating >= star ? Icons.star : Icons.star_border,
                  color: AppColors.terracotta,
                  size: 36,
                ),
                onPressed: () => setState(() => _selectedRating = star),
              );
            }),
          ),
          const SizedBox(height: 16),

          // Notes field
          TextField(
            controller: _notesController,
            maxLines: 3,
            style: const TextStyle(color: AppColors.warmIvory),
            decoration: InputDecoration(
              hintText: 'Add a note... (optional)',
              hintStyle: TextStyle(
                color: AppColors.withOpacity(AppColors.warmIvory, 0.5)),
              enabledBorder: OutlineInputBorder(
                borderSide: BorderSide(color: AppColors.chocolateLight),
                borderRadius: BorderRadius.circular(8)),
              focusedBorder: OutlineInputBorder(
                borderSide: BorderSide(color: AppColors.terracotta),
                borderRadius: BorderRadius.circular(8)),
              filled: true,
              fillColor: AppColors.withOpacity(AppColors.warmIvory, 0.05),
            ),
          ),
          const SizedBox(height: 20),

          // Save button
          FilledButton(
            onPressed: _isSaving ? null : _saveFeedback,
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.terracotta,
              foregroundColor: AppColors.warmIvory,
              minimumSize: const Size.fromHeight(48),
            ),
            child: _isSaving
              ? const CircularProgressIndicator(color: AppColors.warmIvory, strokeWidth: 2)
              : const Text('Save'),
          ),
          const SizedBox(height: 8),

          // Skip button
          TextButton(
            onPressed: _isSaving ? null : widget.onComplete,
            style: TextButton.styleFrom(
              foregroundColor: AppColors.withOpacity(AppColors.warmIvory, 0.6),
              minimumSize: const Size.fromHeight(48),
            ),
            child: const Text('Skip'),
          ),
        ],
      ),
    );
  }
}
```

### RecipeCacheService Extensions

Key: `palateful_cook_logs_{recipeId}` stores a JSON list of `{recipe_id, rating, cooked_at}` entries.

```dart
static const _cookLogsKeyPrefix = 'palateful_cook_logs_';

Future<void> logCook(String recipeId, int rating, DateTime cookedAt) async {
  try {
    final prefs = await SharedPreferences.getInstance();
    final key = _cookLogsKeyPrefix + recipeId;
    final existing = prefs.getString(key);
    final List<dynamic> logs =
        existing != null ? jsonDecode(existing) as List<dynamic> : [];
    logs.add({
      'recipe_id': recipeId,
      'rating': rating,
      'cooked_at': cookedAt.toIso8601String(),
    });
    await prefs.setString(key, jsonEncode(logs));
  } catch (e) {
    debugPrint('RecipeCacheService: failed to log cook $recipeId: $e');
  }
}

Future<List<Map<String, dynamic>>> getCookLogs(String recipeId) async {
  try {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_cookLogsKeyPrefix + recipeId);
    if (raw == null) return [];
    final list = jsonDecode(raw) as List<dynamic>;
    return list.cast<Map<String, dynamic>>();
  } catch (e) {
    debugPrint('RecipeCacheService: failed to get cook logs $recipeId: $e');
    return [];
  }
}
```

### Offline Note Handling — Piggybacks on Story 6.4 Infrastructure

`RecipeCacheService.queueNoteAdd()` already exists from Story 6.4. When `isOffline == true` in the feedback sheet, queue the note instead of calling the API directly. The `_syncPendingNotes()` in `CookModeScreen.didChangeAppLifecycleState` will flush the queue on next app resume.

The `isOffline` bool comes directly from `_CookModeScreenState._isOffline` (set during initial load if no network). Pass it into `PostCookFeedbackSheet`.

### SharedPreferences Key Namespace — Full Registry

All Palateful keys use `palateful_` prefix:
- `palateful_recipe_{recipeId}` — cached recipe JSON (Story 6.4)
- `palateful_pending_notes` — queued note additions (Story 6.4)
- `palateful_cook_logs_{recipeId}` — cook log history (this story)

### Navigation After Feedback Sheet

`showModalBottomSheet` returns a `Future` that completes when the sheet closes. Using `await`:

```dart
await showModalBottomSheet(...);
if (mounted) context.pop(); // Only pop after sheet is dismissed
```

`context.pop()` from cook mode returns the user to the recipe detail screen. Route: `/recipes/:id/cook` → pop → `/recipes/:id` (detail).

### UX Spec Notes

- Dark cooking mode theme: `AppColors.chocolateDark` sheet background, `AppColors.warmIvory` text
- Stars: `AppColors.terracotta` (warm, consistent with timer chips and offline indicator)
- No star selected is valid — user can save without rating (only notes) or skip entirely
- `isScrollControlled: true` ensures notes field is not covered by keyboard (MediaQuery.viewInsets.bottom padding)
- 48dp minimum touch targets on all buttons (cooking mode accessibility standard from AC: NFR23)

### What NOT To Do

- Do NOT add a new API endpoint for cook logs in this story — local storage is sufficient
- Do NOT change routing for cook mode — `context.pop()` is the correct exit
- Do NOT rewrite CookModeScreen to Riverpod — keep setState pattern
- Do NOT show the feedback sheet on `_exitCookMode()` (back button / X) — only on "Done cooking"
- Do NOT block the sheet from closing if the API call fails — always call `onComplete`

### Testing Pattern for `PostCookFeedbackSheet`

Since the sheet takes `apiClient` and `recipeCache` as constructor params (not via DI), tests can inject mock/stub versions directly:

```dart
testWidgets('Skip button fires onComplete', (tester) async {
  SharedPreferences.setMockInitialValues({});
  bool completed = false;
  final cache = RecipeCacheService();

  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: PostCookFeedbackSheet(
        recipeId: 'r1',
        recipeName: 'Pasta',
        apiClient: _MockApiClient(), // or use a real ApiClient with stubbed dio
        recipeCache: cache,
        isOffline: false,
        onComplete: () => completed = true,
      ),
    ),
  ));

  await tester.tap(find.text('Skip'));
  await tester.pumpAndSettle();

  expect(completed, isTrue);
});
```

For `ApiClient`, since it uses `Dio` under the hood and tests don't have a live server, test the `PostCookFeedbackSheet` with `isOffline: true` to bypass the API call in save tests.

### References

- [Source: app/lib/features/recipes/cook_mode/cook_mode_screen.dart:330] — `_finishCooking()` to replace
- [Source: app/lib/features/recipes/cook_mode/cook_mode_screen.dart:350] — `_showTimerDetailSheet()` pattern to follow for modal bottom sheet
- [Source: app/lib/core/services/recipe_cache_service.dart] — Extend with `logCook` / `getCookLogs`; `queueNoteAdd` already exists
- [Source: app/lib/core/services/api_client.dart:437] — `addRecipeNote(String recipeId, String body)` — existing endpoint for note submission
- [Source: app/lib/features/recipes/cook_mode/widgets/] — Place new widget here alongside `step_navigator.dart` and `ingredient_strip.dart`
- [Source: _bmad-output/implementation-artifacts/6-4-offline-cooking-mode.md] — `RecipeCacheService`, `queueNoteAdd`, `isOffline` state, offline queue sync infrastructure
- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.5] — Story requirements
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md] — Dark cook mode theme (chocolate #4A3728 bg, warm ivory #F5ECD7 text, terracotta for interactive), 48dp touch targets (NFR23)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

None.

### Completion Notes List

- `apiClient` made nullable (`ApiClient?`) to support test harness that passes `null` when `isOffline: true`
- 9 tests implemented (4 unit + 5 widget), all passing
- Full regression suite: 122 tests passing

### Code Review

**M1 (FIXED)**: Silent note data loss — when `isOffline == false` but `apiClient == null`, `?.addRecipeNote` silently returned null instead of queuing. Fixed: fall through to `queueNoteAdd` when apiClient is absent.

**M2 (DOCUMENTED)**: `_finishCooking()` integration path untested — CookModeScreen integration test requires significant DI mocking infrastructure beyond story scope. Acceptable known limitation.

**L1 (FIXED)**: Unused `_FakeApiClient` class removed from `post_cook_feedback_test.dart`.

**L2 (FIXED)**: `_isSaving` now reset to `false` via `setState()` before calling `onComplete()`. Allows tests to use `pumpAndSettle` cleanly; eliminates the `pump(Duration(milliseconds: 100))` workaround.

**L3 (DOCUMENTED)**: `isOffline` snapshot in sheet doesn't reflect mid-session connectivity restore — acceptable trade-off; `_syncPendingNotes()` on resume handles queued notes.

### File List

- app/lib/core/services/recipe_cache_service.dart
- app/lib/features/recipes/cook_mode/cook_mode_screen.dart
- app/lib/features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart
- app/test/post_cook_feedback_test.dart
