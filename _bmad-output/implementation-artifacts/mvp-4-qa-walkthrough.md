# QA Walkthrough: MVP.4 — Filter Pill + Bottom Sheet

## What shipped

1. **`FilterPill` widget** (`app/lib/features/home/widgets/filter_pill.dart`) — small tappable pill with a tune icon, label, and chevron. Displays `"Filter"` when no filters are active; `"Filter ($n)"` with a primary-color background when `$n > 0`. Left-aligned inside the home screen content.
2. **`FilterBottomSheet` widget** (`app/lib/features/home/widgets/filter_bottom_sheet.dart`) — modal bottom sheet with:
   - Drag handle
   - "Filters" title
   - **Meals** section: `Wrap` of chips for All / Breakfast / Lunch / Dinner / Dessert / Snack
   - **Vibes** section: `Wrap` of chips for All + every entry in `defaultVibeOptions`
   - Footer row: `Clear all` on the left, `Apply` on the right
   - Internal **draft state** so chip taps inside the sheet don't commit to the parent screen until Apply is tapped. Drag-down dismiss = cancel (draft thrown away).
   - Static `FilterBottomSheet.show(...)` helper so the home screen doesn't need to know about `showModalBottomSheet`.
3. **`home_screen.dart`** — replaced the stacked `MealFilterBar` + `VibeFilterBar` at lines 468-477 with a single `FilterPill`. New method `_openFilterSheet` and computed getter `_activeFilterCount` support it. The legacy `_onMealFilterChanged` / `_onVibeFilterChanged` handlers are removed (filter state is now committed via the sheet's `onApply` callback).
4. **Removed import** of `vibe_filter_bar.dart` from `home_screen.dart` since it's no longer used on that screen (still referenced by `recipe_book_detail_screen.dart`, which is untouched).
5. **Widget tests** — 6 new tests in `filter_pill_test.dart`:
   - `FilterPill` renders `"Filter"` when `activeCount == 0`
   - `FilterPill` renders `"Filter (2)"` when `activeCount == 2`
   - `FilterPill` tap invokes `onTap` callback
   - `FilterBottomSheet` renders Meals + Vibes sections with chip content
   - `FilterBottomSheet` Apply fires `onApply` with draft selections and closes
   - `FilterBottomSheet` Clear all resets draft without closing the sheet

## UX details worth knowing

- Filter chips use a `Wrap` layout inside the bottom sheet — multi-row, space-efficient for a tall sheet — instead of the horizontal scroll used by the old bars.
- **Neither `MealFilterBar` nor `VibeFilterBar` was deleted**. They still live in `lib/features/home/widgets/meal_filter_bar.dart` and `lib/shared/widgets/vibe_filter_bar.dart` (the latter is still imported by `recipe_book_detail_screen.dart`). This story only removes them from the home screen.
- The active-count formula is `(meal != .all ? 1 : 0) + (vibe != null ? 1 : 0)`, matching the existing filter-state conventions on `home_screen.dart`.
- Drag-down cancel works because `onApply` is only invoked from the Apply button — the sheet's draft state is discarded when the sheet is popped without calling it.
- `_openFilterSheet` is async but uses `await` so a future developer could chain post-close work; currently nothing is chained.

## QA checklist

### Automated
- [x] `flutter test test/features/home/filter_pill_test.dart` — **6/6 pass**
- [x] `flutter test test/features/home/home_screen_test.dart` — **4/4 pass** (no regression to mvp-3)
- [x] `flutter analyze lib/features/home/home_screen.dart lib/features/home/widgets/filter_pill.dart lib/features/home/widgets/filter_bottom_sheet.dart` — clean (only pre-existing `home_screen.dart` warnings remain)

### Manual (to run post-deploy)
- [ ] Open the home screen. Confirm the two stacked filter bars are gone and a single `[🎛 Filter ▾]` pill appears left-aligned where they used to be.
- [ ] Tap the pill → bottom sheet slides up with Meals + Vibes sections.
- [ ] Tap `Dinner` in Meals, `Comfort` in Vibes. Tap Apply. Sheet closes. Recipe grid re-loads with both filters applied. Pill now reads `Filter (2)` with a filled background.
- [ ] Tap the pill again. The draft inside the sheet should reflect the currently-committed state (Dinner + Comfort still highlighted).
- [ ] Tap Clear all inside the sheet. Chips reset to "All". Sheet stays open.
- [ ] Tap Apply. Sheet closes. Pill returns to plain `Filter` label.
- [ ] Re-open the sheet, tap a chip, then drag down to dismiss (without Apply). Pill should still reflect the previous committed state.

### Known tradeoffs / follow-ups
- **No sort option in the sheet** — the existing `SortChips` row is still rendered separately below the pill. Intentional: sort is a separate concern and not part of the meal/vibe filtering scope.
- **No new filter types** added in this story (difficulty, cook time, tags). Scope was deliberately kept to "rehome existing filters into a bottom sheet."
- **`MealFilterBar` is now unused** by the codebase but kept in case a future screen wants the horizontal-scroll variant. Safe to delete in a follow-up tech-debt pass if nothing starts using it.
- **Pre-existing home_screen.dart warnings** (unused `chat_provider.dart` import, two underscore-name infos, unused `colorScheme` in `_buildErrorState`) are left alone.

## Files touched

- `app/lib/features/home/widgets/filter_pill.dart` (new)
- `app/lib/features/home/widgets/filter_bottom_sheet.dart` (new)
- `app/lib/features/home/home_screen.dart` (modified — import swap, pill render, `_openFilterSheet`, `_activeFilterCount`, removed old handlers)
- `app/test/features/home/filter_pill_test.dart` (new — 6 widget tests)
- `_bmad-output/implementation-artifacts/mvp-4-qa-walkthrough.md` (new)
