# Story 6.2: Gesture Navigation for Messy Hands

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to navigate between cooking steps using swipe gestures and large tap targets,
so that I can interact with the app when my hands are messy.

## Acceptance Criteria

1. Given I am in cooking mode, when I swipe left/right, then I navigate to the next/previous step
2. Given I am in cooking mode, then all interactive elements have minimum 64dp touch targets
3. Given I am in cooking mode, then a progress indicator shows which step I'm on (e.g., "1 of 8")
4. Given I am in cooking mode, when I tap the left or right edge of the step area, then I navigate backward or forward (alternative to swiping)
5. Given I am in cooking mode, when I navigate between steps, then haptic feedback fires on every step transition

## Tasks / Subtasks

- [x] Task 1: Add left/right edge tap zones to step content area (AC: #4, #5)
  - [x] In `CookModeScreen`, add `onTapUp` to the existing `GestureDetector` that wraps `_buildStepContent()`
  - [x] If `details.localPosition.dx < screenWidth * 0.25`: call `_previousStep()` (guard: only when `_currentStep > 0`)
  - [x] If `details.localPosition.dx > screenWidth * 0.75`: call `_nextStep()` (guard: only when `_currentStep < _steps.length - 1`)
  - [x] Use `MediaQuery.of(context).size.width` inside the `onTapUp` callback for screen width
  - [x] Haptic feedback already fires via `_goToStep()` → `HapticFeedback.selectionClick()` — no additional haptic needed

- [x] Task 2: Increase StepNavigator nav button height to 64dp (AC: #2)
  - [x] In `step_navigator.dart`, change `_NavButton` padding from `symmetric(horizontal: 20, vertical: 14)` to `symmetric(horizontal: 20, vertical: 22)` to achieve ≥64dp total height
  - [x] Verify `Prev` and `Next`/`Done` buttons are visually correct after the height change

- [x] Task 3: Increase header IconButton touch targets to 64dp (AC: #2)
  - [x] In `cook_mode_screen.dart` `_buildHeader()`, add `constraints: const BoxConstraints(minWidth: 64, minHeight: 64)` to both the back `IconButton` and the close `IconButton`
  - [x] Verify header still lays out correctly with the larger tap target

- [x] Task 4: Increase IngredientStrip expand/collapse tap target to 64dp (AC: #2)
  - [x] In `ingredient_strip.dart`, change the expand/collapse `GestureDetector`'s inner `Padding` from `const EdgeInsets.all(8)` to `const EdgeInsets.symmetric(horizontal: 8, vertical: 23)` to bring total target height to ≥64dp
  - [x] Verify expand/collapse still works correctly

- [x] Task 5: Widget tests (AC: #1–#5)
  - [x] Test that `onTapUp` on left 25% triggers `_previousStep` (test via widget test with `WidgetTester.tapAt`)
  - [x] Test that `onTapUp` on right 75%+ triggers `_nextStep`
  - [x] Test StepNavigator Prev button renders with sufficient height (≥64dp via `tester.getSize`)
  - [x] Test IngredientStrip expand/collapse target has height ≥64dp

## Dev Notes

### Critical Context: This Is a Brownfield Story

**All cook mode files are fully implemented from Story 6.1.** Do NOT rewrite anything from scratch.

The three files to modify:
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` — add `onTapUp` + header constraints
- `app/lib/features/recipes/cook_mode/widgets/step_navigator.dart` — button padding
- `app/lib/features/recipes/cook_mode/widgets/ingredient_strip.dart` — expand/collapse target

### What Already Works (DO NOT CHANGE)

- **Swipe navigation**: `GestureDetector` with `onHorizontalDragEnd` (threshold ±500) — AC #1 ✅
- **Haptic feedback**: `HapticFeedback.selectionClick()` fires inside `_goToStep()` — AC #5 ✅
- **Step progress indicator**: 32px step number "X of Y" display — AC #3 ✅
- StepNavigator prev/next buttons, step dots, long-press to mark all complete ✅
- Wake lock, active timers, ingredient check-off ✅

### Task 1 Detail: Adding onTapUp to Existing GestureDetector

The step content is currently wrapped in:
```dart
// cook_mode_screen.dart — the Expanded section
Expanded(
  child: GestureDetector(
    onHorizontalDragEnd: (details) { ... },
    child: _buildStepContent(),
  ),
),
```

Add `onTapUp` alongside `onHorizontalDragEnd`:
```dart
Expanded(
  child: GestureDetector(
    onHorizontalDragEnd: (details) { /* existing — do not change */ },
    onTapUp: (details) {
      final screenWidth = MediaQuery.of(context).size.width;
      final tapX = details.localPosition.dx;
      if (tapX < screenWidth * 0.25) {
        if (_currentStep > 0) _previousStep();
      } else if (tapX > screenWidth * 0.75) {
        if (_currentStep < _steps.length - 1) _nextStep();
      }
    },
    child: _buildStepContent(),
  ),
),
```

**Interaction note:** `onTapUp` fires when the user lifts their finger without dragging. It won't conflict with `onHorizontalDragEnd` because Flutter's gesture arena resolves them separately — a drag cancels the tap, a tap completes when no drag occurs.

**The middle 50% of the screen has no tap action** — intentional, prevents accidental navigation while reading.

### Task 2 Detail: StepNavigator Button Padding

Current `_NavButton` in `step_navigator.dart`:
```dart
child: Padding(
  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
  // Row with icon + text (approximately 20px height)
)
```
Total button height: 14 + 14 + ~20 ≈ 48dp. Below 64dp minimum.

Fix:
```dart
padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 22),
// Total: 22 + 22 + ~20 ≈ 64dp ✅
```

### Task 3 Detail: Header IconButton Constraints

Flutter's default `IconButton` minSize is 48dp. Cook mode requires 64dp.

Current:
```dart
IconButton(
  icon: const Icon(Icons.arrow_back, color: AppColors.warmIvory),
  onPressed: _exitCookMode,
),
```

Fix (apply to BOTH back and close buttons):
```dart
IconButton(
  icon: const Icon(Icons.arrow_back, color: AppColors.warmIvory),
  onPressed: _exitCookMode,
  constraints: const BoxConstraints(minWidth: 64, minHeight: 64),
  padding: EdgeInsets.zero,
),
```

### Task 4 Detail: IngredientStrip Expand/Collapse Target

Current expand/collapse `GestureDetector` in `ingredient_strip.dart`:
```dart
GestureDetector(
  onTap: () {
    HapticFeedback.selectionClick();
    setState(() => _isExpanded = !_isExpanded);
  },
  child: Padding(
    padding: const EdgeInsets.all(8),  // ← too small
    child: Row(children: [Text(...), Icon(...)]),
  ),
),
```
Total height: 8 + 8 + ~24px text ≈ 40dp. Below 64dp minimum.

Fix:
```dart
child: Padding(
  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 16),
  child: Row(children: [Text(...), Icon(...)]),
),
```
Total: 16 + 16 + ~24 ≈ 56dp. Still a bit short. Alternatively, `vertical: 20` gives ≈ 64dp:
```dart
padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 20),
```

### State Management: Use setState (NOT Riverpod)

The architecture doc specifies Riverpod 3.0, but the entire cook mode implementation uses `setState`. Do NOT introduce Riverpod. All state changes remain in `_CookModeScreenState`.

### AppColors Usage: Stay Consistent

CookModeScreen intentionally uses `AppColors.*` (not `colorScheme.*`). Do not change any color usage.

### Test Pattern

Follow the "equivalent widget tree" pattern used in all Epic 2/6 tests — build a minimal widget structure. See `app/test/cook_mode_test.dart` for the pattern used in Story 6.1.

For the `onTapUp` tap zone test:
```dart
// Test left tap zone triggers previous step
final state = tester.state<_CookModeScreenState>(find.byType(CookModeScreen));
// Start at step 1
await tester.tapAt(Offset(50, 400)); // x=50 → left zone on 800px screen
// ... verify step changed
```

For size verification:
```dart
final size = tester.getSize(find.byType(_NavButton-widget-or-key));
expect(size.height, greaterThanOrEqualTo(64));
```

### UX Context: Why These Changes Matter

From UX spec (Cooking Mode Accessibility):
> "Phone lies flat on the counter, viewed from above at ~60° angle and arm's length. Requires large type, high contrast, minimal content per screen, and **oversized touch/swipe targets**."
> "64dp touch targets, **full-width swipe zones**, voice control"
> "Swipe has tap alternative (**arrow buttons at screen edges**)"

The left/right tap zones simulate the "arrow buttons at screen edges" pattern — the user can tap the far left or right of the screen with a wet finger rather than precisely hitting a small button.

### DO NOT:
- Implement background timer notifications (Story 6.3) — timers work in-app only for now
- Implement offline caching (Story 6.4)
- Implement post-cook feedback flow (Story 6.5)
- Change the swipe threshold (±500) — it's calibrated and working
- Add visual arrows or indicators for the tap zones — invisible zones only (tap-only, no visual)
- Migrate to Riverpod
- Modify `_goToStep()`, `_nextStep()`, or `_previousStep()` logic
- Add voice control (future Story 6.x)

### References

- [Source: app/lib/features/recipes/cook_mode/cook_mode_screen.dart] — Main screen to modify (Tasks 1, 3)
- [Source: app/lib/features/recipes/cook_mode/widgets/step_navigator.dart] — _NavButton padding (Task 2)
- [Source: app/lib/features/recipes/cook_mode/widgets/ingredient_strip.dart] — Expand target (Task 4)
- [Source: app/test/cook_mode_test.dart] — Test pattern from Story 6.1
- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.2] — Story requirements
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Cooking-Step-Card] — "64dp minimum touch targets. Swipe has tap alternative (arrow buttons at screen edges)"
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Cooking-Mode-Accessibility] — Touch target table

## Code Review Action Items

- [x] [AI-Review][LOW] `cook_mode_screen.dart`: Invisible tap zones (left/right 25%) had no code comment — future devs couldn't understand why middle taps do nothing. Fixed: added two-line comment above `onTapUp` explaining the zone split.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

- Added `onTapUp` to existing `GestureDetector` in cook_mode_screen.dart — left 25% → prev, right 25% → next, middle 50% ignored
- Haptic feedback flows through existing `_goToStep()` → `HapticFeedback.selectionClick()`, no additional code needed
- `_NavButton` vertical padding: 14 → 22, giving ~64dp button height (22+22+~20px content)
- Header IconButtons: added `constraints: BoxConstraints(minWidth: 64, minHeight: 64), padding: EdgeInsets.zero`
- IngredientStrip expand/collapse: padding `all(8)` → `symmetric(h:8, v:23)`, giving 64dp height (23+23+~18px icon)
- 5 new tests, 83 total — all pass, 0 regressions

### File List

**Modified files:**
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` — onTapUp tap zones + 64dp header constraints
- `app/lib/features/recipes/cook_mode/widgets/step_navigator.dart` — _NavButton vertical padding 14→22
- `app/lib/features/recipes/cook_mode/widgets/ingredient_strip.dart` — expand/collapse padding to 64dp

**New files:**
- `app/test/cook_mode_gesture_test.dart` — 5 gesture navigation widget tests
