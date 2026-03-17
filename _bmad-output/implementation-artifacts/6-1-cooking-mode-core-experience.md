# Story 6.1: Cooking Mode Core Experience

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to enter a hands-free cooking mode with large text, one step per screen, and an ingredient reference strip,
so that I can follow a recipe without squinting or scrolling while cooking.

## Acceptance Criteria

1. Given I am viewing any recipe, when I tap "Start Cooking", then cooking mode activates with the **dark theme** (chocolate `#4A3728` background, warm ivory `#F5ECD7` text) and minimal chrome
2. Given I am in cooking mode, then one step is displayed per screen with **24px+ step instruction text** and a **32px step number** prominently displayed
3. Given I am in cooking mode, then a floating ingredient strip is accessible for quick reference (tap to expand/collapse)
4. Given I am in cooking mode, then the **screen wake lock is enabled** so the display stays on
5. Given I am in cooking mode, when I navigate between steps, then transitions respond within 200ms and provide haptic feedback

## Tasks / Subtasks

- [x] Task 1: Fix steps data source — use structured `recipe['steps']` list (AC: #2)
  - [x] Replace `_parseInstructions(recipe['instructions'])` call in `_loadRecipe()` with direct extraction from `recipe['steps']` list
  - [x] Sort by `step_number` before extracting instructions (API returns them sorted but be defensive)
  - [x] Change `_steps` type from `List<String>` to `List<String>` — no type change needed, just fix the source
  - [x] Remove the now-unused `_parseInstructions()` method entirely
  - [x] Verify `_buildStepContent()` and timer detection still work with structured steps (they only use the instruction string — no changes needed)

- [x] Task 2: Apply dark theme throughout CookModeScreen (AC: #1)
  - [x] Change Scaffold `backgroundColor` from `AppColors.cream` to `AppColors.chocolate` (`#4A3728`)
  - [x] Change loading state `backgroundColor` from `AppColors.cream` to `AppColors.chocolate`
  - [x] Change error state `backgroundColor` from `AppColors.cream` to `AppColors.chocolate`; update error container colors to use dark-mode appropriate tints
  - [x] In `_buildHeader()`: change background container to `AppColors.chocolate`; update text/icon colors to `AppColors.warmIvory` or `AppColors.cream`
  - [x] In `_buildStepContent()`: update step number/indicator text color to `AppColors.cream`; change step card background from `AppColors.warmWhite` to `AppColors.chocolateDark`; update instruction text color to `AppColors.warmIvory`; update completed state colors to dark-mode variants
  - [x] In `_buildInlineTimer()`: foreground colors for dark background (terracotta works on dark bg, no change needed)
  - [x] Ensure swipe hint icon/text visible on dark background (using warmIvory at 40% opacity)

- [x] Task 3: Upsize step number and instruction text (AC: #2)
  - [x] Replace the "Step X of Y" text (`fontSize: 14`) with a large step number display: `Text('${_currentStep + 1}', style: TextStyle(fontSize: 32, fontWeight: FontWeight.w700, color: AppColors.warmIvory))`
  - [x] Add a small "of ${_steps.length}" label beside or below the 32px number in a smaller font (~14px)
  - [x] Increase instruction `Text` `fontSize` from `18` to `24` in `_buildStepContent()`
  - [x] Increase `height` (line height) to `1.5` for the 24px text

- [x] Task 4: Widget tests (AC: #1–#5)
  - [x] Test CookModeScreen renders step instruction text — verify `Text` widget with step content exists
  - [x] Test CookModeScreen shows "Step 1 of N" indicator (or large step number + total)
  - [x] Test IngredientStrip renders ingredient names (existing widget test pattern)
  - [x] Test StepNavigator renders Next and Done buttons appropriately

## Dev Notes

### Critical Context: This Is a Brownfield Story

**CookModeScreen IS SUBSTANTIALLY IMPLEMENTED.** The full screen exists at `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`. Its companion widgets exist:
- `app/lib/features/recipes/cook_mode/widgets/ingredient_strip.dart` — collapsible ingredient strip with check-off
- `app/lib/features/recipes/cook_mode/widgets/step_navigator.dart` — prev/next buttons + step dots

**Do NOT rewrite from scratch.** This story is three targeted fixes + tests.

### Bug #1 (CRITICAL): Wrong Steps Data Source

The existing `_loadRecipe()` reads `recipe['instructions']` (a legacy plain text field) and tries to parse it into steps using regex:

```dart
// CURRENT — BROKEN with Story 2.1 structured steps
_steps = _parseInstructions(recipe['instructions'] ?? '');
```

Story 2.1 (done) replaced plain-text instructions with a structured `steps` list: each step is `{step_number: int, instruction: String}`. The current cook mode ignores these entirely, showing either an empty list or old-format data.

**Fix:**
```dart
// CORRECT
final stepsData = recipe['steps'] as List? ?? [];
stepsData.sort((a, b) =>
    (a['step_number'] as int? ?? 0).compareTo(b['step_number'] as int? ?? 0));
_steps = stepsData.map((s) => s['instruction'] as String? ?? '').toList();
```

Delete `_parseInstructions()` — it becomes dead code.

### Bug #2: Wrong Background Theme

AC #1 requires dark chocolate background (`#4A3728`). Current code uses `AppColors.cream` (a light beige). The UX spec calls for a "warm dark mode" for cooking. The cook mode should feel immersive and distinct from the regular app light theme.

`AppColors` definitions to use:
```dart
// app/lib/core/theme/app_colors.dart — check these constants exist
AppColors.chocolate  // #4A3728 — use as main background
AppColors.warmIvory  // #F5ECD7 — use for primary text (check exact name)
AppColors.cream      // fallback for text if warmIvory doesn't exist
```

Read `app_colors.dart` before implementing to confirm exact constant names matching the hex values.

### Gap #3: Step Text Size

- Step number: currently "Step X of Y" at 14px → needs a large **32px** number
- Instruction text: currently 18px → needs **24px minimum**

The `_buildStepContent()` method renders both. Only the font sizes change; the layout structure can stay.

### State Management: Use setState (NOT Riverpod)

The architecture doc specifies Riverpod 3.0, but the **entire Epic 2 implementation uses `setState`** — HomeScreen, RecipeBooksScreen, RecipeDetailScreen, EditRecipeScreen, CookModeScreen itself. Do NOT introduce Riverpod. Use `setState` for all state changes in this story, consistent with the existing `_CookModeScreenState` implementation.

### AppColors Usage: Stay Consistent

Unlike Epic 2 screens which migrated to `colorScheme.*`, **CookModeScreen intentionally uses `AppColors.*`** (same exception as `RecipeCard`). This is by design — cook mode has custom palette colors (chocolate, terracotta, sage) that aren't in the Material 3 colorScheme. Keep using `AppColors.*` throughout.

### Existing Functionality to Preserve (DO NOT BREAK)

The following already works correctly — do not modify:
- Wake lock: `WakelockPlus.enable()` / `WakelockPlus.disable()` in init/dispose ✅
- Swipe gesture navigation: `GestureDetector` with `onHorizontalDragEnd` (threshold ±500) ✅
- Active timers: `_ActiveTimer` + `_timerTick` periodic tick ✅
- Ingredient strip: collapse/expand, check-off via `_checkedIngredients` ✅
- `StepNavigator`: step dots, prev/next, long-press to mark all complete ✅
- Haptic feedback on step transitions ✅
- Cooking stopwatch ✅
- Inline timer detection via regex on instruction text ✅

### What the "Start Cooking" FAB Does

`RecipeDetailScreen` has a `FloatingActionButton.extended` labeled "Start Cooking":
```dart
// recipe_detail_screen.dart
onPressed: _startCooking,
// ...
void _startCooking() {
  context.push('/recipes/${widget.recipeId}/cook');
}
```
Router wires `/recipes/:id/cook` → `CookModeScreen(recipeId: id)`. No changes needed here.

### Data Contract: GetRecipe Response

`GET /v1/recipes/{id}` returns (from Story 2.1):
```json
{
  "id": "...",
  "name": "...",
  "ingredients": [
    {
      "ingredient": {"canonical_name": "Garlic"},
      "quantity_display": "3",
      "unit_display": "cloves"
    }
  ],
  "steps": [
    {"step_number": 1, "instruction": "Mince the garlic..."},
    {"step_number": 2, "instruction": "Heat oil in pan..."}
  ],
  "is_favorite": true,
  "can_edit": true
}
```

### Flutter Architecture

- **State management**: `setState` (consistent with all Epic 2 screens)
- **Navigation**: GoRouter — `context.push('/recipes/$id/cook')` from detail screen
- **API client**: `getIt<ApiClient>().getRecipe(recipeId)` — already used in cook mode
- **Theme**: AppColors.* (intentional exception from colorScheme migration)
- **Wake lock**: `wakelock_plus` — already imported and working
- **Haptics**: `HapticFeedback.selectionClick()` on step nav (already in place)

### Test Pattern

Follow "equivalent widget tree" pattern used in all Epic 2 tests — no DI mocking, just build a minimal widget structure. See `app/test/recipe_crud_test.dart` or `app/test/recipe_books_test.dart` for examples.

```dart
// Example test structure
await tester.pumpWidget(
  MaterialApp(
    home: Scaffold(
      body: Column(
        children: [
          Text('Step 1 of 3', ...),
          Text('Mince the garlic and set aside...', style: TextStyle(fontSize: 24)),
        ],
      ),
    ),
  ),
);
expect(find.text('Mince the garlic and set aside...'), findsOneWidget);
```

### DO NOT:
- Implement gesture navigation (Story 6.2) — swipe already exists, do not change
- Implement background timer notifications (Story 6.3) — timers work in-app only for now
- Implement offline caching (Story 6.4)
- Implement post-cook feedback flow (Story 6.5)
- Migrate to Riverpod
- Modify the backend API (cook mode is read-only, no new endpoints needed)
- Add a timer management sheet or custom timer input — the inline timer button that auto-detects time in step text is sufficient for this story

### References

- [Source: app/lib/features/recipes/cook_mode/cook_mode_screen.dart] — Main screen (brownfield, modify in-place)
- [Source: app/lib/features/recipes/cook_mode/widgets/ingredient_strip.dart] — Ingredient strip widget
- [Source: app/lib/features/recipes/cook_mode/widgets/step_navigator.dart] — Step navigator widget
- [Source: app/lib/core/theme/app_colors.dart] — Color constants (read before implementing dark theme)
- [Source: app/lib/features/recipes/recipe_detail_screen.dart] — "Start Cooking" FAB entry point
- [Source: app/lib/core/router/app_router.dart:123-133] — Cook mode route `/recipes/:id/cook`
- [Source: services/api/src/api/v1/recipe/get_recipe.py] — GetRecipe response includes `steps` list
- [Source: app/test/recipe_crud_test.dart] — Test pattern reference
- [Source: _bmad-output/planning-artifacts/epics.md#Epic-6] — Full Epic 6 context

## Code Review Action Items

- [x] [AI-Review][LOW] `cook_mode_screen.dart:84`: `stepsData.sort()` mutated the API response list in place — `recipe['steps']` is a reference to `response.data`'s list. Fixed: wrap with `List<dynamic>.from()` to sort a copy.
- [x] [AI-Review][LOW] `cook_mode_screen.dart:88`: `s['instruction'] as String? ?? ''` could produce empty strings when `instruction` is null — blank step cards would appear. Fixed: added `.where((s) => s.isNotEmpty)` filter, consistent with the removed `_parseInstructions()` method.
- [x] [AI-Review][LOW] `cook_mode_screen.dart:97`: Error message `'Failed to load recipe: $e'` exposes raw exception details to users. Pre-existing; acceptable for MVP but should use user-friendly message in a future cleanup pass.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

- Replaced `_parseInstructions(recipe['instructions'])` with structured `recipe['steps']` list extraction + sort by `step_number`; deleted dead `_parseInstructions()` method
- All scaffold/state backgrounds changed to `AppColors.chocolate` (#4A3728)
- Header uses `AppColors.chocolate` bg, `AppColors.warmIvory` text/icons, `AppColors.chocolateDark` timer badge
- Step card background: `AppColors.chocolateDark`; completed state: sage tint on dark; instruction text: `AppColors.warmIvory`
- Divider changed from `AppColors.divider` to `AppColors.chocolateLight`
- Step number: 32px `AppColors.warmIvory`; "of N" label: 14px `AppColors.cream`; instruction: 24px height 1.5
- Swipe hint uses `AppColors.warmIvory` at 40% opacity
- `_buildInlineTimer()` and `_buildActiveTimers()`: terracotta already works on dark background, no color changes needed
- 4/4 widget tests pass

### File List

**Modified files:**
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` — Data source fix, dark theme, text sizing

**New files:**
- `app/test/cook_mode_test.dart` — 4 widget tests
