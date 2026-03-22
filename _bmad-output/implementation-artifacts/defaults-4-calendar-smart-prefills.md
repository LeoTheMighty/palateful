# Story Defaults.4: Calendar Meal Planning — Smart Pre-fills & Quick Add

Status: complete

## Story

As a user,
I want to add meals to my calendar quickly with smart pre-filled defaults and the option to type free-text meals,
so that meal planning feels effortless and I'm not forced to browse recipes just to log "eating out."

## Acceptance Criteria

1. Calendar screen has a FAB ("+") that opens a meal creation flow
2. Each day row has a small "+" button that opens meal creation with the date pre-filled
3. Meal type is pre-selected based on time of day (before 10am → Breakfast, 10am-2pm → Lunch, 2pm-8pm → Dinner, after 8pm → Snack)
4. Users can type a free-text meal name without selecting a recipe (e.g., "Eating out", "Leftovers")
5. Recent free-text entries appear as quick-select chips for fast re-use
6. Recipe selection is optional — users can search/browse recipes OR just type a name
7. Empty day states show actionable "Plan a meal" tap target instead of passive "No meals planned" text
8. Long-press on events shows options (reschedule/remove) — existing behavior preserved

## Tasks / Subtasks

- [x] Task 1: Add FAB to calendar screen (AC: #1)
  - [x] Modify `app/lib/features/calendar/calendar_screen.dart`
  - [x] Add FloatingActionButton matching the pattern used on other screens
  - [x] FAB opens the enhanced PlanMealSheet with today's date and time-inferred meal type

- [x] Task 2: Add per-day "+" buttons (AC: #2)
  - [x] In `_buildDayColumn`, add a small "+" IconButton in the day header row
  - [x] Tapping opens PlanMealSheet with that day's date pre-filled

- [x] Task 3: Time-aware meal type pre-selection (AC: #3)
  - [x] When opening PlanMealSheet without explicit meal type:
    - `DateTime.now().hour < 10` → Breakfast
    - `10 <= hour < 14` → Lunch
    - `14 <= hour < 20` → Dinner
    - `hour >= 20` → Snack
  - [x] Pre-select in the meal type selector, user can still change

- [x] Task 4: Enhance PlanMealSheet for free-text + optional recipe (AC: #4, #6)
  - [x] Modify `app/lib/features/calendar/widgets/plan_meal_sheet.dart`
  - [x] Make `recipeId` optional (API already supports this)
  - [x] Add a text field for meal name (pre-filled with recipe name if recipe selected)
  - [x] Add "Search recipes" button/section that opens recipe search
  - [x] Allow saving with just a name and no recipe

- [x] Task 5: Quick-select chips for recent free-text meals (AC: #5)
  - [x] Store recent free-text meal names locally (SharedPreferences, max ~10)
  - [x] Display as horizontal chip row above the text field in PlanMealSheet
  - [x] Tapping a chip fills in the name instantly

- [x] Task 6: Improve empty day states (AC: #7)
  - [x] Replace "No meals planned" text with tappable widget
  - [x] Show: "Tap to plan a meal" with a subtle "+" icon
  - [x] Tapping opens PlanMealSheet with that day pre-filled

- [x] Task 7: Verify existing behaviors preserved (AC: #8)
  - [x] Long-press on events still shows reschedule/remove options
  - [x] Tapping an event still navigates to recipe detail
  - [x] Weekly shopping list generation still works

## Dev Notes

- The PlanMealSheet currently requires `recipeId` as a required param — the main change is making it optional
- The API's `CreateMealEvent.Params` already has `recipe_id` as optional, so no backend changes needed
- FAB pattern exists on 5 other screens — follow the same style
- Quick-select chips use SharedPreferences for simplicity — no backend needed
- This story is independent of Stories 1-3 (no default shopping/book dependency)

### References

- [Investigation: 08-calendar-meal-planning-ux.md]
- [Epic: epic-smart-defaults.md]
