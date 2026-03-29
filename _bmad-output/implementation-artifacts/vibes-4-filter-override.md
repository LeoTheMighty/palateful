# Story Vibes.4: Flutter — Vibe Filter Bar + User Override

Status: complete

## Story

As a user,
I want to browse recipes by vibe ("I'm in the mood for something light") and change a recipe's vibe if the AI got it wrong,
so that vibes are useful for discovery and reflect my personal perception of each recipe.

## Acceptance Criteria

1. Vibe filter bar appears on the home screen recipe browsing area (horizontal scrolling chips)
2. Filter options: All (default) + 7 vibes, loaded from the API options endpoint
3. Selecting a vibe filters the recipe list to show only recipes with that vibe (primary or secondary)
4. Filter works alongside existing meal type filter and sort options
5. On recipe detail screen: tapping a vibe chip opens a small picker to change/remove vibes
6. User can set primary vibe, optional secondary vibe, or clear both
7. Changes are saved via `PUT /recipes/{id}` and reflect immediately in the UI
8. Vibe filter bar uses the same vibe colors as the VibeChip pills (colored when selected, muted when not)

## Tasks / Subtasks

- [x] Task 1: Create VibeFilterBar widget (AC: #1, #2, #8)
  - [x] Create `app/lib/shared/widgets/vibe_filter_bar.dart`
  - [x] Horizontal scrolling list of filter chips (same pattern as `MealFilterBar`)
  - [x] First chip: "All" (no filter, default selected)
  - [x] Remaining chips: one per vibe from `vibeOptionsProvider`
  - [x] Selected chip: filled with vibe color
  - [x] Unselected chip: outlined/muted
  - [x] Returns selected vibe ID (or null for "All") via callback

- [x] Task 2: Integrate filter on home screen (AC: #1, #3, #4)
  - [x] Add `VibeFilterBar` to the home screen, positioned near existing `MealFilterBar` / `SortChips`
  - [x] Wire selected vibe into the recipe query: pass `?vibe=comfort` parameter
  - [x] If a vibe is selected AND a meal filter is selected, both apply (AND logic)
  - [x] Ensure the filter works with the recipe book detail screen too (if browsing within a book)

- [x] Task 3: Vibe override on recipe detail (AC: #5, #6, #7)
  - [x] On recipe detail screen: make vibe chips tappable
  - [x] Tapping opens a small bottom sheet or inline picker showing all 7 vibes
  - [x] User can:
    - Tap a vibe to set as primary (if different from current)
    - Tap a second vibe to set as secondary
    - Tap the current primary to clear it
    - "Clear all" option to remove vibes entirely
  - [x] Save via `PUT /recipes/{id}` with updated vibe fields
  - [x] Update local state immediately (optimistic UI)

- [x] Task 4: Recipe book detail — vibe filter (AC: #4)
  - [x] Add `VibeFilterBar` to recipe book detail screen (same pattern as home screen)
  - [x] Filter recipes within the book by vibe

## Dev Notes

- `VibeFilterBar` follows the exact same pattern as `MealFilterBar` — horizontal scroll, single-select, callback
- The vibe override bottom sheet should be minimal: 7 colored chips in a 2-row grid, with the current selection highlighted
- Optimistic UI: update the recipe in local state immediately, then fire the API call. On failure, revert
- The filter query is just adding `?vibe=X` to existing recipe list API calls — minimal work
- Consider: should the vibe filter persist across app restarts? Probably not — default to "All" each session

### References

- [Investigation: 10-health-vibes-score.md — Vibe Filter + User Override sections]
- [Epic: epic-vibes.md]
