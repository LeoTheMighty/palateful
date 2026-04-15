# Story MVP.4: Filter Redesign — Filter Pill + Bottom Sheet

Status: ready-for-dev

## Story

As a user on the home screen,
I want a single "Filter" pill that opens a bottom sheet containing meal and vibe filters,
so that the main screen breathes instead of showing two stacked horizontally-scrolling chip rows that feel cramped and strangely organized.

## Context

The home screen currently stacks **two separate filter bars** vertically at `home_screen.dart:468-477`:

- `MealFilterBar` (`app/lib/features/home/widgets/meal_filter_bar.dart`) — horizontal chip scroll for meal types (Breakfast, Lunch, Dinner, Dessert, Snack, …)
- `VibeFilterBar` (`app/lib/shared/widgets/vibe_filter_bar.dart`) — horizontal colored chip scroll for vibes

Stacked together they consume ~120 logical pixels of vertical space, double-scroll, and compete for attention. Leo's subjective feedback during Party Mode: "meals and vibes are really strangely organized and the UI is cramped."

Per Sally's UX recommendation (Option 3 from Party Mode), this story replaces both bars with a single `[🎛 Filter ▾]` pill that triggers a bottom sheet containing both filter sections, with an active-filter count badge on the pill when filters are applied. Reference: modern food apps like Yummly and Paprika use the same pattern.

## Acceptance Criteria

1. `MealFilterBar` and `VibeFilterBar` are no longer rendered inline on the home screen — the widget invocations at `home_screen.dart:468-477` are removed.
2. A new `FilterPill` widget is rendered on the home screen in the approximate vertical position where the filter bars used to live, aligned to the leading edge.
3. The pill displays text "Filter" with a trailing chevron-down icon.
4. When one or more filters are active, the pill displays a count badge (e.g., `Filter (2)`) and visually indicates the active state (e.g., filled background color).
5. Tapping the pill opens a modal bottom sheet containing:
   - A **Meals** section header with the existing meal filter chips (reuse `MealFilterBar`'s chip content, not its wrapper)
   - A **Vibes** section header with the existing vibe filter chips (reuse `VibeFilterBar`'s chip content)
   - A sticky footer with two buttons: `Clear all` (resets both filters) and `Apply` (dismisses the sheet, applies the selection)
6. Filter state is held in the same `_mealFilter` and `_vibeFilter` state variables at `home_screen.dart:46-47` — this story does not change the filter data model or the downstream filtering logic.
7. `Apply` dismisses the sheet and triggers the existing recipe grid filter update. `Clear all` resets both filters to their default (`null` / "All") but does NOT auto-dismiss the sheet.
8. Dragging the sheet down dismisses it without applying (behaves as cancel, reverting any chip taps made since opening).
9. `meal_filter_bar.dart` and `vibe_filter_bar.dart` continue to exist as widgets — they are reused inside the bottom sheet. This story **does not delete** those files.
10. Widget tests cover: (a) tapping the pill opens the sheet, (b) the pill shows the correct count badge when filters are active, (c) tapping Apply dismisses the sheet and updates home screen filter state, (d) tapping Clear all resets selections in the sheet.

## Tasks / Subtasks

- [ ] Task 1: Create the `FilterPill` widget (AC: #2, #3, #4)
  - [ ] New file: `app/lib/features/home/widgets/filter_pill.dart`
  - [ ] Stateless widget taking `activeCount: int`, `onTap: VoidCallback`
  - [ ] Rendering: pill shape (rounded rectangle), `Filter` text, trailing chevron icon
  - [ ] Active state: when `activeCount > 0`, show `Filter ($activeCount)` and use a filled/primary background; when zero, use outlined/neutral background
  - [ ] Match existing theme tokens — do not hardcode colors. Grep for existing pill styles in the app (likely in `app/lib/shared/widgets/` or theme files) and reuse spacing/radius values

- [ ] Task 2: Create the filter bottom sheet (AC: #5, #7, #8)
  - [ ] New file: `app/lib/features/home/widgets/filter_bottom_sheet.dart`
  - [ ] Stateful widget or `showModalBottomSheet` helper that takes initial `MealFilter?` and `VibeFilter?` values plus `onApply(meal, vibe)` callback
  - [ ] Internal draft state: track pending meal and vibe selections separately from the home screen's committed state so drag-down cancel works
  - [ ] Layout:
    - Title: "Filters"
    - Meals section: header text + reused meal chip content from `MealFilterBar`
    - Vibes section: header text + reused vibe chip content from `VibeFilterBar`
    - Sticky footer with `TextButton('Clear all')` and `FilledButton('Apply')`
  - [ ] `Apply`: invoke `onApply(draftMeal, draftVibe)` then `Navigator.pop(context)`
  - [ ] `Clear all`: reset `draftMeal = null; draftVibe = null;` — do NOT pop
  - [ ] Drag-down dismiss: no callback fired, home screen state remains unchanged (this is the default `showModalBottomSheet` behavior, so verify existing chip taps in the sheet only mutate draft state, not parent state)

- [ ] Task 3: Reuse existing filter bar chip content inside the sheet (AC: #5, #9)
  - [ ] Either: extract the chip-building logic from `meal_filter_bar.dart` and `vibe_filter_bar.dart` into shared builder functions callable from both the old bar widgets AND the new bottom sheet, OR: directly instantiate `MealFilterBar` and `VibeFilterBar` inside the bottom sheet (simpler, but uses the horizontal-scroll layout)
  - [ ] Recommended: wrap chips in a `Wrap` widget inside the sheet (multi-row, space-efficient for a vertical sheet) rather than the horizontal scroll used in the bars. Extract chip builder if needed
  - [ ] Do NOT delete `MealFilterBar` or `VibeFilterBar` — they may be reused elsewhere, and this story only removes them from the home screen
  - [ ] Grep for other usages of `MealFilterBar` and `VibeFilterBar` before assuming they are home-screen-only

- [ ] Task 4: Wire up the home screen (AC: #1, #6, #7)
  - [ ] Modify `app/lib/features/home/home_screen.dart` around lines 468-477
  - [ ] Remove the `MealFilterBar` and `VibeFilterBar` widget invocations
  - [ ] In their place, render the `FilterPill` — compute `activeCount` as `(mealFilter != null ? 1 : 0) + (vibeFilter != null ? 1 : 0)` (adjust based on how "All" is represented)
  - [ ] `onTap` opens the bottom sheet via `showModalBottomSheet`, passing current `_mealFilter` and `_vibeFilter`, and an `onApply` callback that calls `setState` with the new values
  - [ ] Verify the recipe grid downstream of the filter state still updates correctly on Apply

- [ ] Task 5: Widget tests (AC: #10)
  - [ ] Test location: `app/test/features/home/filter_pill_test.dart` and `app/test/features/home/filter_bottom_sheet_test.dart` (create if missing)
  - [ ] Pill tests: renders "Filter" with zero active, renders "Filter (2)" with both active, tapping invokes callback
  - [ ] Bottom sheet tests: opens on pill tap, selecting a chip updates draft state only, Apply invokes `onApply` with selections and closes sheet, Clear all resets draft without closing, drag-down dismiss does not invoke `onApply`
  - [ ] Home screen integration test: after Apply, the committed filter state matches the sheet selection

## Dev Notes

- **Do not delete `meal_filter_bar.dart` or `vibe_filter_bar.dart` in this story.** They may be reused by the bottom sheet directly or by other screens. Grep first.
- Use a `Wrap` layout for chips inside the sheet instead of horizontal scroll — a vertical sheet has more width-per-row and users can see all options without scrolling.
- **Draft state is load-bearing.** If chip taps inside the sheet directly mutate home screen state, drag-down dismiss would leave the app in a half-applied state. Always commit via `Apply` only.
- Do NOT add new filter capabilities (tags, difficulty, cook time) in this story — scope is strictly "rehome existing filters into a bottom sheet."
- **Merge order**: land MVP.3 before this story. MVP.3 edits the top of `home_screen.dart`; this story edits the middle/lower sections around line 468. Landing them in order avoids merge conflicts.
- The active-count formula in Task 4 may need adjustment — confirm how "no filter" is represented (`null`, `MealFilter.all`, etc.) by reading the current `_mealFilter` / `_vibeFilter` usage in `home_screen.dart:46-47`.
- Semantic label on the pill: `'Filter recipes'` with state announcement when count > 0.

### Project Structure Notes

- New widgets go under `app/lib/features/home/widgets/` matching existing convention (`meal_filter_bar.dart` lives there).
- Flutter test convention: `app/test/features/home/`.
- Bottom sheet helper can live alongside the widget or inside it — pick whichever matches existing patterns in the codebase (grep `showModalBottomSheet` to see how other features structure it).

### References

- Home screen render site: `app/lib/features/home/home_screen.dart:468-477`
- Filter state vars: `home_screen.dart:46-47` (`_mealFilter`, `_vibeFilter`)
- Meal filter bar: `app/lib/features/home/widgets/meal_filter_bar.dart`
- Vibe filter bar: `app/lib/shared/widgets/vibe_filter_bar.dart`
- [Epic: epic-mvp-finalization.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
